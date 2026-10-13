"""Cloud Tasks queue service with local async worker fallback."""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from google.cloud import tasks_v2

from app.config import settings

logger = logging.getLogger(__name__)


class QueueService:
    """Manages dispatching tasks to Cloud Tasks or running them locally."""

    def __init__(self) -> None:
        self.use_mock = False
        self.client: tasks_v2.CloudTasksClient | None = None
        self._local_handler: Callable[[str], Any] | None = None

        if (
            settings.gcp_project_id
            and settings.gcp_project_id != "local-dev-project"
            and settings.cloud_tasks_queue
        ):
            try:
                self.client = tasks_v2.CloudTasksClient()
                self.queue_path = self.client.queue_path(
                    settings.gcp_project_id,
                    settings.gcp_region,
                    settings.cloud_tasks_queue,
                )
                logger.info("Connected to Cloud Tasks queue: %s", self.queue_path)
            except Exception as e:
                logger.warning(
                    "Failed to connect to Cloud Tasks (%s). Using local task execution.",
                    e,
                )
                self.use_mock = True
        else:
            self.use_mock = True

    def register_local_handler(self, handler: Callable[[str], Any]) -> None:
        """Register a local function to execute tasks when in local development mode."""
        self._local_handler = handler

    async def enqueue_task(self, task_id: str) -> None:
        """Enqueue a task for processing."""
        if self.use_mock or not self.client:
            logger.info(
                "Local mode: Spawning background execution for task %s", task_id
            )
            if self._local_handler:
                # Trigger asynchronously
                if asyncio.iscoroutinefunction(self._local_handler):
                    asyncio.create_task(self._local_handler(task_id))
                else:
                    loop = asyncio.get_running_loop()
                    loop.run_in_executor(None, self._local_handler, task_id)
            else:
                logger.warning("No local task handler registered for task %s", task_id)
            return

        payload = {"task_id": task_id}
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": settings.worker_service_url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode(),
            }
        }
        response = self.client.create_task(
            parent=self.queue_path, task=task  # type: ignore[arg-type]
        )
        logger.info("Enqueued task %s to Cloud Tasks (%s)", task_id, response.name)


_queue_service_instance: QueueService | None = None


def get_queue_service() -> QueueService:
    global _queue_service_instance
    if _queue_service_instance is None:
        _queue_service_instance = QueueService()
    return _queue_service_instance
