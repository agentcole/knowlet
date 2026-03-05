import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.config import settings

logger = logging.getLogger(__name__)


def _smtp_ready() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)


def _send_sync(message: EmailMessage) -> None:
    smtp_client: smtplib.SMTP | smtplib.SMTP_SSL

    if settings.SMTP_USE_SSL:
        smtp_client = smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        )
    else:
        smtp_client = smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        )

    with smtp_client as server:
        if not settings.SMTP_USE_SSL and settings.SMTP_USE_TLS:
            server.starttls()

        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

        server.send_message(message)


async def send_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> bool:
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return False

    if not _smtp_ready():
        logger.warning(
            "Email notifications are enabled but SMTP settings are incomplete"
        )
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["To"] = to_email
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message.set_content(text_body)

    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        await asyncio.to_thread(_send_sync, message)
    except Exception:
        logger.exception("Failed to send email notification")
        return False

    return True


async def send_member_invited_email(
    to_email: str,
    full_name: str,
    tenant_name: str,
    role: str,
) -> bool:
    subject = f"Added to {tenant_name} on Knowlet"
    text_body = (
        f"Hi {full_name},\n\n"
        f"You were added to the tenant \"{tenant_name}\" on Knowlet with role \"{role}\".\n"
        f"Sign in here: {settings.APP_BASE_URL}\n\n"
        "If this was unexpected, contact your tenant admin."
    )
    return await send_email(to_email, subject, text_body)


async def send_member_role_changed_email(
    to_email: str,
    full_name: str,
    tenant_name: str,
    previous_role: str,
    new_role: str,
) -> bool:
    subject = f"Role updated in {tenant_name}"
    text_body = (
        f"Hi {full_name},\n\n"
        f"Your role in tenant \"{tenant_name}\" changed from \"{previous_role}\" to \"{new_role}\".\n"
        f"Open Knowlet: {settings.APP_BASE_URL}"
    )
    return await send_email(to_email, subject, text_body)


async def send_member_removed_email(
    to_email: str,
    full_name: str,
    tenant_name: str,
) -> bool:
    subject = f"Removed from {tenant_name}"
    text_body = (
        f"Hi {full_name},\n\n"
        f"You were removed from tenant \"{tenant_name}\" on Knowlet.\n"
        f"If this seems incorrect, contact your tenant owner."
    )
    return await send_email(to_email, subject, text_body)
