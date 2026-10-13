"""Multi-channel notification dispatcher."""

import logging

from app.models.task import TaskRecord
from app.notify.email import notify_email
from app.notify.notion_comment import notify_in_notion
from app.notify.slack import notify_slack
from app.services.firestore import get_firestore_service

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Dispatches completion notifications to configured channels."""

    @staticmethod
    async def dispatch_all(task: TaskRecord) -> None:
        """Send notifications to all requested channels for the task."""
        firestore = get_firestore_service()
        channels = task.notify_channels or ["notion_comment"]

        for channel in channels:
            channel_clean = channel.lower().strip()
            success = False
            try:
                if channel_clean == "notion_comment":
                    # Determine target page ID
                    target_id = None
                    if task.target_page_ids:
                        target_id = task.target_page_ids[0]
                    elif task.created_links:
                        target_id = task.created_links[0].id

                    if target_id:
                        success = await notify_in_notion(task, target_id)
                    else:
                        logger.info(
                            "No Notion page available to post comment notification."
                        )
                        success = False
                elif channel_clean == "slack":
                    success = await notify_slack(task)
                elif channel_clean == "email":
                    success = await notify_email(task)
                else:
                    logger.warning("Unknown notification channel: %s", channel)
                    success = False
            except Exception as e:
                logger.exception(
                    "Failed to dispatch notification to %s: %s", channel, e
                )
                success = False

            delivery_status = "delivered" if success else "failed"
            firestore.record_notification_delivery(
                task.id, channel_clean, delivery_status
            )
