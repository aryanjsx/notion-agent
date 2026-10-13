"""FastAPI routes for task creation, inspection, and human confirmation."""

import logging
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.agent.loop import get_agent_loop
from app.models.task import (
    ConfirmationRequest,
    TaskCreateRequest,
    TaskRecord,
    TaskResponse,
    TaskStatus,
)
from app.services.firestore import get_firestore_service
from app.services.queue import get_queue_service
from app.services.storage import get_storage_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/worker/execute")
async def execute_worker_task(payload: dict):
    """Worker endpoint invoked by Cloud Tasks to process a queued task."""
    task_id = payload.get("task_id")
    if not task_id:
        raise HTTPException(status_code=400, detail="Missing task_id in worker payload")
    agent_loop = get_agent_loop()
    result = await agent_loop.run(task_id)
    return {"status": result.status.value if result else "not_found", "task_id": task_id}


@router.post("", response_model=TaskResponse, status_code=202)
async def create_task(req: TaskCreateRequest):
    """Submit a new task for the Notion AI Agent to process asynchronously."""
    firestore = get_firestore_service()
    queue = get_queue_service()

    # 1. Idempotency Check
    if req.idempotency_key:
        existing_task_id = firestore.check_idempotency(req.idempotency_key)
        if existing_task_id:
            existing_task = firestore.get_task(existing_task_id)
            if existing_task:
                logger.info(
                    "Idempotency match for key %s -> Returning existing task %s",
                    req.idempotency_key,
                    existing_task_id,
                )
                return TaskResponse(
                    task_id=existing_task.id,
                    status=existing_task.status,
                    prompt=existing_task.prompt,
                    mode=existing_task.mode,
                    plan=existing_task.plan,
                    steps=existing_task.steps,
                    created_links=existing_task.created_links,
                    summary=existing_task.summary,
                    error_message=existing_task.error_message,
                    suggested_fix=existing_task.suggested_fix,
                    duration_seconds=existing_task.duration_seconds,
                    created_at=existing_task.created_at,
                    updated_at=existing_task.updated_at,
                )

    # 2. Create Task Record
    task_id = str(uuid.uuid4())
    task = TaskRecord(
        id=task_id,
        prompt=req.prompt,
        attachments=req.attachments or [],
        target_page_ids=req.target_page_ids or [],
        notify_channels=req.notify_channels or ["notion_comment"],
        mode=req.mode,
        idempotency_key=req.idempotency_key,
        status=TaskStatus.QUEUED,
    )
    firestore.create_task(task)

    if req.idempotency_key:
        firestore.record_idempotency(req.idempotency_key, task_id)

    # 3. Enqueue for background execution
    await queue.enqueue_task(task_id)

    return TaskResponse(
        task_id=task.id,
        status=task.status,
        prompt=task.prompt,
        mode=task.mode,
        plan=[],
        steps=[],
        created_links=[],
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """Get the current status, step execution log, and output links for a task."""
    firestore = get_firestore_service()
    task = firestore.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse(
        task_id=task.id,
        status=task.status,
        prompt=task.prompt,
        mode=task.mode,
        plan=task.plan,
        steps=task.steps,
        created_links=task.created_links,
        summary=task.summary,
        error_message=task.error_message,
        suggested_fix=task.suggested_fix,
        duration_seconds=task.duration_seconds,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running or queued task."""
    firestore = get_firestore_service()
    task = firestore.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    firestore.update_task_status(
        task_id, status=TaskStatus.CANCELLED, summary="Task cancelled by user."
    )
    return {"message": f"Task {task_id} has been cancelled."}


@router.post("/{task_id}/confirm")
async def confirm_task_action(task_id: str, req: ConfirmationRequest):
    """Approve or reject a pending human confirmation gate."""
    agent_loop = get_agent_loop()
    updated = await agent_loop.resume_with_confirmation(
        task_id, approved=req.approved, feedback=req.feedback
    )
    if not updated:
        raise HTTPException(
            status_code=404, detail="Task not found or not awaiting confirmation"
        )
    return {"status": updated.status.value, "task_id": updated.id}


@router.post("/upload")
async def upload_attachment(file: UploadFile = File(...)):
    """Upload a document attachment (PDF, DOCX, TXT, CSV) to storage."""
    storage = get_storage_service()
    content = await file.read()
    dest_name = f"{uuid.uuid4()}_{file.filename}"
    uri = storage.upload_bytes(
        content, dest_name, content_type=file.content_type or "application/octet-stream"
    )
    return {"filename": file.filename, "storage_uri": uri, "size_bytes": len(content)}
