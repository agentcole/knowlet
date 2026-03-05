import asyncio
import json
import logging
import mimetypes
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.meeting import MeetingRecording, MeetingStatus
from app.services.meeting_service import save_transcript
from app.services.llm_service import MEETING_SUMMARY_PROMPT, generate_text
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_session_factory():
    engine = create_async_engine(settings.DATABASE_URL)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _guess_audio_mimetype(storage_path: str) -> str:
    guessed, _ = mimetypes.guess_type(storage_path)
    return guessed or "application/octet-stream"


def _parse_summary_payload(raw_text: str) -> dict:
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    candidates: list[str] = [clean]

    fenced_json = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL | re.IGNORECASE)
    if fenced_json:
        candidates.insert(0, fenced_json.group(1).strip())

    first_brace = raw_text.find("{")
    last_brace = raw_text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidates.append(raw_text[first_brace:last_brace + 1].strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue

    raise ValueError("Could not parse meeting summary JSON")


async def _process_meeting(meeting_id: str, tenant_id: str):
    session_factory = _get_session_factory()
    tid = uuid.UUID(tenant_id)

    async with session_factory() as db:
        result = await db.execute(
            select(MeetingRecording).where(MeetingRecording.id == uuid.UUID(meeting_id))
        )
        meeting = result.scalar_one_or_none()
        if not meeting:
            return

        meeting.status = MeetingStatus.TRANSCRIBING
        await db.commit()

        try:
            # Read audio file
            from app.services.storage_service import storage
            audio_data = await storage.read(meeting.storage_path)

            # Transcribe with Deepgram
            full_text = ""
            segments = []

            try:
                from deepgram import DeepgramClient, PrerecordedOptions

                dg = DeepgramClient(settings.DEEPGRAM_API_KEY)
                options = PrerecordedOptions(
                    model="nova-3",
                    smart_format=True,
                    diarize=True,
                    punctuate=True,
                )

                source = {
                    "buffer": audio_data,
                    "mimetype": _guess_audio_mimetype(meeting.storage_path),
                }
                response = dg.listen.rest.v("1").transcribe_file(source, options)

                # Extract transcript
                results = response.results
                if results and results.channels:
                    channel = results.channels[0]
                    if channel.alternatives:
                        full_text = channel.alternatives[0].transcript or ""

                    # Extract diarized segments
                    if channel.alternatives and channel.alternatives[0].words:
                        current_speaker = None
                        current_text = ""
                        current_start = 0

                        for word in channel.alternatives[0].words:
                            speaker = f"Speaker {word.speaker}" if hasattr(word, 'speaker') else "Speaker 0"
                            if speaker != current_speaker:
                                if current_text:
                                    segments.append({
                                        "speaker": current_speaker,
                                        "start": current_start,
                                        "end": word.start,
                                        "text": current_text.strip(),
                                    })
                                current_speaker = speaker
                                current_start = word.start
                                current_text = word.punctuated_word or word.word
                            else:
                                current_text += " " + (word.punctuated_word or word.word)

                        if current_text:
                            segments.append({
                                "speaker": current_speaker,
                                "start": current_start,
                                "end": word.end,
                                "text": current_text.strip(),
                            })

                if results and hasattr(results, 'metadata') and results.metadata:
                    meeting.duration_seconds = results.metadata.duration

            except ImportError:
                full_text = "[Deepgram SDK not available - transcript placeholder]"
            except Exception as e:
                full_text = f"[Transcription failed: {e}]"

            meeting.status = MeetingStatus.SUMMARIZING
            await db.commit()

            # Summarize with LLM
            summary = None
            action_items = []

            try:
                llm_result = await generate_text(
                    MEETING_SUMMARY_PROMPT,
                    f"Transcript:\n\n{full_text[:15000]}",
                )
                data = _parse_summary_payload(llm_result)
                summary = str(data.get("summary", "")).strip()
                raw_action_items = data.get("action_items", [])
                if isinstance(raw_action_items, list):
                    action_items = [item for item in raw_action_items if isinstance(item, dict)]
                else:
                    action_items = []
            except Exception as exc:
                logger.warning("Meeting summary generation failed for %s: %s", meeting.id, exc)
                summary = "Summary generation failed."

            # Save transcript
            await save_transcript(
                db, tid, meeting.id, full_text, segments, summary, action_items
            )

            meeting.status = MeetingStatus.PROCESSED
            await db.commit()

            # Update wiki with meeting references
            try:
                from app.services.wiki_service import create_page

                page_content = f"""# Meeting: {meeting.title}

**Date:** {meeting.meeting_date or meeting.created_at}
**Participants:** {', '.join(meeting.participants or ['Unknown'])}

## Summary
{summary or 'No summary available.'}

## Action Items
"""
                for item in action_items:
                    if isinstance(item, dict):
                        page_content += f"- **{item.get('assignee', 'Unassigned')}**: {item.get('task', '')}"
                        if item.get('deadline'):
                            page_content += f" (Due: {item['deadline']})"
                        page_content += "\n"

                page_content += f"\n## Transcript\n{full_text}"

                page = await create_page(db, tid, f"Meeting: {meeting.title}", page_content)
                page.source_meetings = [str(meeting.id)]
                await db.commit()
            except Exception as exc:
                logger.warning("Failed writing meeting wiki page for %s: %s", meeting.id, exc)

        except Exception as e:
            logger.exception("Meeting processing failed for %s: %s", meeting_id, e)
            meeting.status = MeetingStatus.FAILED
            await db.commit()


@celery_app.task(name="process_meeting", bind=True, max_retries=3)
def process_meeting(self, meeting_id: str, tenant_id: str):
    try:
        asyncio.run(_process_meeting(meeting_id, tenant_id))
    except Exception as exc:
        self.retry(exc=exc, countdown=60)
