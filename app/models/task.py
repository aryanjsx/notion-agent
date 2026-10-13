"""Task data models and schemas."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskMode(str, Enum):
    AUTO = "auto"
    CONFIRM_BEFORE_WRITE = "confirm_before_write"


class TaskStep(BaseModel):
    step_number: int
    title: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    status: str = "pending"  # pending, running, completed, failed, skipped
    output: Any | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CreatedLink(BaseModel):
    title: str
    url: str
    id: str | None = None
    type: str = "page"  # page, database, block, comment


class TaskCreateRequest(BaseModel):
    prompt: str = Field(
        ..., description="Plain-language description of what to do in Notion"
    )
    attachments: list[str] | None = Field(
        default_factory=list, description="File paths or GCS URIs"
    )
    target_page_ids: list[str] | None = Field(
        default_factory=list, description="Specific Notion page/db IDs"
    )
    notify_channels: list[str] | None = Field(
        default_factory=lambda: ["notion_comment"], description="Notification channels"
    )
    mode: TaskMode = Field(default=TaskMode.AUTO, description="Execution mode")
    idempotency_key: str | None = Field(
        default=None, description="Client-provided idempotency key"
    )


class ConfirmationRequest(BaseModel):
    approved: bool
    feedback: str | None = None


class TaskRecord(BaseModel):
    id: str
    prompt: str
    status: TaskStatus = TaskStatus.QUEUED
    mode: TaskMode = TaskMode.AUTO
    attachments: list[str] = Field(default_factory=list)
    target_page_ids: list[str] = Field(default_factory=list)
    notify_channels: list[str] = Field(default_factory=lambda: ["notion_comment"])
    idempotency_key: str | None = None
    plan: list[str] = Field(default_factory=list)
    steps: list[TaskStep] = Field(default_factory=list)
    created_links: list[CreatedLink] = Field(default_factory=list)
    summary: str | None = None
    error_message: str | None = None
    suggested_fix: str | None = None
    duration_seconds: float | None = None
    pending_action: dict[str, Any] | None = None
    notification_delivery: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    prompt: str
    mode: TaskMode
    plan: list[str] = Field(default_factory=list)
    steps: list[TaskStep] = Field(default_factory=list)
    created_links: list[CreatedLink] = Field(default_factory=list)
    summary: str | None = None
    error_message: str | None = None
    suggested_fix: str | None = None
    duration_seconds: float | None = None
    created_at: datetime
    updated_at: datetime
