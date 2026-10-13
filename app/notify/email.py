"""Email notification dispatcher (SendGrid / SMTP API)."""

import logging

import httpx

from app.config import settings
from app.models.task import TaskRecord, TaskStatus

logger = logging.getLogger(__name__)


async def notify_email(task: TaskRecord, recipient_email: str | None = None) -> bool:
    """Send completion email via SendGrid or log if not configured."""
    api_key = settings.sendgrid_api_key
    to_email = recipient_email or "user@example.com"

    if not api_key:
        logger.info(
            "[Mock Email] Notification for task %s sent to %s (Status: %s)",
            task.id,
            to_email,
            task.status.value,
        )
        return True

    status_str = "SUCCESS" if task.status == TaskStatus.SUCCEEDED else "FAILURE"
    subject = f"[Notion Agent] Task {status_str}: {task.prompt[:40]}..."

    links_html = (
        "".join(
            f"<li><a href='{link.url}'>{link.title}</a></li>"
            for link in task.created_links
        )
        or "None"
    )
    content_html = f"""
    <h2>Notion AI Agent Task Report</h2>
    <p><strong>Status:</strong> {task.status.value}</p>
    <p><strong>Prompt:</strong> {task.prompt}</p>
    <p><strong>Summary:</strong> {task.summary or "Task processed."}</p>
    <h3>Created / Updated Notion Pages:</h3>
    <ul>{links_html}</ul>
    """

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": settings.notification_from_email, "name": "Notion AI Agent"},
        "subject": subject,
        "content": [{"type": "text/html", "value": content_html}],
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            return resp.status_code in (200, 202)
    except Exception as e:
        logger.exception("Failed to send email via SendGrid: %s", e)
        return False
