from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.core.language import language_name, normalize_language

_llm: ChatAnthropic | None = None


def get_llm() -> ChatAnthropic:
    global _llm
    if _llm is None:
        _llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=4096,
        )
    return _llm


async def generate_text(system_prompt: str, user_prompt: str) -> str:
    llm = get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = await llm.ainvoke(messages)
    content = response.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
                else:
                    parts.append(str(block))
        return "".join(parts)
    return str(content)


async def stream_text(system_prompt: str, user_prompt: str, history: list[dict] | None = None):
    llm = get_llm()
    messages = [SystemMessage(content=system_prompt)]
    if history:
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                from langchain_core.messages import AIMessage
                messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=user_prompt))

    async for chunk in llm.astream(messages):
        if chunk.content:
            yield chunk.content


def with_output_language(system_prompt: str, language_code: str | None) -> str:
    lang = language_name(normalize_language(language_code))
    return (
        f"{system_prompt}\n\n"
        "Output Language Requirement:\n"
        f"- Write all user-facing content in {lang}.\n"
    )


WIKI_ORGANIZE_PROMPT = """You are a knowledge base organizer. Given document content, organize it into wiki categories and pages.

Return a JSON object with this structure:
{
  "categories": [
    {
      "name": "Category Name",
      "pages": [
        {
          "title": "Page Title",
          "content": "Full markdown content for this page"
        }
      ]
    }
  ]
}

Rules:
- Create logical categories based on the content topics
- Each page should be self-contained and well-structured in markdown
- Preserve all important information from the source
- Use clear, descriptive titles
- If content doesn't fit a category, use "General" category
"""

WIKI_PLACEMENT_PROMPT = """You suggest wiki placement for a newly uploaded document.

Return ONLY valid JSON with this structure:
{
  "category_name": "Category",
  "page_title": "Page title",
  "action": "create_new|append|replace",
  "reasoning": "short explanation",
  "confidence": 0.0
}

Rules:
- Prefer an existing category and existing page when it clearly matches.
- Use action "append" if this is an incremental update for an existing page.
- Use action "replace" only when this document should fully supersede an existing page.
- Use action "create_new" when no existing page is a good fit.
- Keep confidence between 0 and 1.
- If uncertain, choose category "General" and action "create_new".
"""

MEETING_SUMMARY_PROMPT = """Summarize this meeting transcript. Include:
1. A brief overview (2-3 sentences)
2. Key discussion points
3. Decisions made
4. Action items (as a JSON array of {"assignee": "name", "task": "description", "deadline": "if mentioned"})

Return ONLY valid JSON (no markdown fences, no extra prose):
{
  "summary": "...",
  "action_items": [...]
}
"""

CHAT_SYSTEM_PROMPT = """You are a helpful knowledge base assistant. Answer questions based on the provided context from the company's knowledge base.

Context from knowledge base:
{context}

Rules:
- Answer based on the provided context
- If the context doesn't contain enough information, say so
- Be concise and helpful
- Reference source pages when relevant
- Include a short "Sources" section at the end with 1-3 source titles you used
- Format responses in markdown
"""
