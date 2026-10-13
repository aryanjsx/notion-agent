"""Slack webhook notification dispatcher."""

import logging

import httpx

from app.config import settings
from app.models.task import TaskRecord, TaskStatus

logger = logging.getLogger(__name__)


async def notify_slack(task: TaskRecord, webhook_url: str | None = None) -> bool:
    """Send formatted notification to Slack via incoming webhook."""
    url = webhook_url or settings.slack_webhook_url
    if not url:
        logger.info("Slack webhook URL not configured, skipping Slack notification.")
        return False

    status_icon = "🟢" if task.status == TaskStatus.SUCCEEDED else "🔴"
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{status_icon} Notion AI Agent: {task.status.value.upper()}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Task ID:*\n`{task.id}`"},
                {
                    "type": "mrkdwn",
                    "text": f"*Duration:*\n{task.duration_seconds or 0:.1f}s",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:*\n{task.summary or 'No summary provided.'}",
            },
        },
    ]

    if task.created_links:
        links_mrkdwn = "\n".join(
            f"• <{link.url}|{link.title}>" for link in task.created_links
        )
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Created / Modified Pages:*\n{links_mrkdwn}",
                },
            }
        )

    if task.error_message:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:* {task.error_message}\n*Suggested Fix:* {task.suggested_fix or 'None'}",
                },
            }
        )

    payload = {"blocks": blocks}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        logger.exception("Failed to send Slack notification: %s", e)
        return False
