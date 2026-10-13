"""Firestore state and persistence service with local fallback."""

import logging
from datetime import UTC, datetime
from typing import Any

from google.cloud import firestore

from app.config import settings
from app.models.task import CreatedLink, TaskRecord, TaskStatus, TaskStep

logger = logging.getLogger(__name__)


class FirestoreService:
    """Manages task records, run logs, and idempotency in Firestore (or in-memory)."""

    def __init__(self) -> None:
        self.use_mock = False
        self._mock_tasks: dict[str, TaskRecord] = {}
        self._mock_idempotency: dict[str, str] = {}
        self.client: firestore.Client | None = None

        if settings.gcp_project_id and settings.gcp_project_id != "local-dev-project":
            try:
                self.client = firestore.Client(
                    project=settings.gcp_project_id,
                    database=settings.firestore_database,
                )
                logger.info(
                    "Connected to Google Cloud Firestore (project: %s)",
                    settings.gcp_project_id,
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize GCP Firestore client (%s). Falling back to local store.",
                    e,
                )
                self.use_mock = True
        else:
            logger.info("Using local in-memory store for Firestore state.")
            self.use_mock = True

    def check_idempotency(self, key: str | None) -> str | None:
        """Check if an idempotency key has already been processed."""
        if not key:
            return None
        if self.use_mock or not self.client:
            return self._mock_idempotency.get(key)
        doc = self.client.collection("idempotency").document(key).get()
        if doc.exists:
            data = doc.to_dict()
            return data.get("task_id") if data else None
        return None

    def record_idempotency(self, key: str | None, task_id: str) -> None:
        """Record an idempotency key mapping to a task ID."""
        if not key:
            return
        if self.use_mock or not self.client:
            self._mock_idempotency[key] = task_id
            return
        self.client.collection("idempotency").document(key).set(
            {
                "task_id": task_id,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )

    def create_task(self, task: TaskRecord) -> TaskRecord:
        """Persist a new task record."""
        if self.use_mock or not self.client:
            self._mock_tasks[task.id] = task.model_copy(deep=True)
            return task

        data = task.model_dump(mode="json")
        self.client.collection("tasks").document(task.id).set(data)
        return task

    def get_task(self, task_id: str) -> TaskRecord | None:
        """Fetch a task record by ID."""
        if self.use_mock or not self.client:
            record = self._mock_tasks.get(task_id)
            return record.model_copy(deep=True) if record else None

        doc = self.client.collection("tasks").document(task_id).get()
        if not doc.exists:
            return None
        return TaskRecord.model_validate(doc.to_dict())

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        summary: str | None = None,
        error_message: str | None = None,
        suggested_fix: str | None = None,
        duration_seconds: float | None = None,
        plan: list[str] | None = None,
        pending_action: dict[str, Any] | None = None,
    ) -> TaskRecord | None:
        """Update overall task status and completion details."""
        now = datetime.now(UTC)
        if self.use_mock or not self.client:
            task = self._mock_tasks.get(task_id)
            if not task:
                return None
            task.status = status
            task.updated_at = now
            if summary is not None:
                task.summary = summary
            if error_message is not None:
                task.error_message = error_message
            if suggested_fix is not None:
                task.suggested_fix = suggested_fix
            if duration_seconds is not None:
                task.duration_seconds = duration_seconds
            if plan is not None:
                task.plan = plan
            if pending_action is not None:
                task.pending_action = pending_action
            return task.model_copy(deep=True)

        updates: dict[str, Any] = {
            "status": status.value,
            "updated_at": now.isoformat(),
        }
        if summary is not None:
            updates["summary"] = summary
        if error_message is not None:
            updates["error_message"] = error_message
        if suggested_fix is not None:
            updates["suggested_fix"] = suggested_fix
        if duration_seconds is not None:
            updates["duration_seconds"] = duration_seconds
        if plan is not None:
            updates["plan"] = plan
        if pending_action is not None:
            updates["pending_action"] = pending_action

        self.client.collection("tasks").document(task_id).update(updates)
        return self.get_task(task_id)

    def add_step(self, task_id: str, step: TaskStep) -> None:
        """Add a step to the task record."""
        if self.use_mock or not self.client:
            task = self._mock_tasks.get(task_id)
            if task:
                task.steps.append(step)
                task.updated_at = datetime.now(UTC)
            return

        doc_ref = self.client.collection("tasks").document(task_id)
        step_dict = step.model_dump(mode="json")
        doc_ref.update(
            {
                "steps": firestore.ArrayUnion([step_dict]),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

    def update_step(
        self,
        task_id: str,
        step_number: int,
        status: str,
        output: Any | None = None,
        error: str | None = None,
    ) -> None:
        """Update status and output of a specific step."""
        now = datetime.now(UTC)
        if self.use_mock or not self.client:
            task = self._mock_tasks.get(task_id)
            if task:
                for s in task.steps:
                    if s.step_number == step_number:
                        s.status = status
                        s.output = output
                        s.error = error
                        s.completed_at = now
                        break
                task.updated_at = now
            return

        # Fetch, update step in memory, and save back to Firestore
        task = self.get_task(task_id)
        if task:
            for s in task.steps:
                if s.step_number == step_number:
                    s.status = status
                    s.output = output
                    s.error = error
                    s.completed_at = now
                    break
            self.client.collection("tasks").document(task_id).update(
                {
                    "steps": [s.model_dump(mode="json") for s in task.steps],
                    "updated_at": now.isoformat(),
                }
            )

    def add_created_link(self, task_id: str, link: CreatedLink) -> None:
        """Record a Notion link created or modified by the agent."""
        now = datetime.now(UTC)
        if self.use_mock or not self.client:
            task = self._mock_tasks.get(task_id)
            if task:
                # Deduplicate by url
                if not any(item.url == link.url for item in task.created_links):
                    task.created_links.append(link)
                task.updated_at = now
            return

        doc_ref = self.client.collection("tasks").document(task_id)
        link_dict = link.model_dump(mode="json")
        doc_ref.update(
            {
                "created_links": firestore.ArrayUnion([link_dict]),
                "updated_at": now.isoformat(),
            }
        )

    def record_notification_delivery(
        self, task_id: str, channel: str, status: str
    ) -> None:
        """Record status of delivery for a notification channel."""
        now = datetime.now(UTC)
        if self.use_mock or not self.client:
            task = self._mock_tasks.get(task_id)
            if task:
                task.notification_delivery[channel] = status
                task.updated_at = now
            return

        self.client.collection("tasks").document(task_id).update(
            {
                f"notification_delivery.{channel}": status,
                "updated_at": now.isoformat(),
            }
        )


_firestore_service_instance: FirestoreService | None = None


def get_firestore_service() -> FirestoreService:
    global _firestore_service_instance
    if _firestore_service_instance is None:
        _firestore_service_instance = FirestoreService()
    return _firestore_service_instance
