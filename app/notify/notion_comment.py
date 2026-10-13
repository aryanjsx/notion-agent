"""In-Notion completion notification via page comment."""

import logging

from app.models.task import TaskRecord, TaskStatus
from app.tools.notion.tools import notion_add_comment

logger = logging.getLogger(__name__)


async def notify_in_notion(task: TaskRecord, target_page_id: str) -> bool:
    """Post completion message as a comment on the target Notion page."""
    status_emoji = (
        "✅"
        if task.status == TaskStatus.SUCCEEDED
        else ("⏸️" if task.status == TaskStatus.AWAITING_CONFIRMATION else "❌")
    )
    links_text = (
        "\n".join(f"- {link.title}: {link.url}" for link in task.created_links)
        or "None"
    )

    comment_body = (
        f"{status_emoji} **Notion AI Agent Update**\n\n"
        f"**Status:** {task.status.value.upper()}\n"
        f"**Prompt:** {task.prompt}\n"
        f"**Summary:** {task.summary or 'Task processed.'}\n\n"
        f"**Artifacts Created/Updated:**\n{links_text}\n"
    )

    if task.error_message:
        comment_body += f"\n**Error:** {task.error_message}"
    if task.suggested_fix:
        comment_body += f"\n**Suggested Fix:** {task.suggested_fix}"
    if task.duration_seconds:
        comment_body += f"\n**Duration:** {task.duration_seconds:.1f}s"

    res = await notion_add_comment(page_id=target_page_id, text=comment_body)
    return res.get("success", False)
