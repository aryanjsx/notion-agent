"""Notion Webhook intake endpoint with signature verification."""

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.routes_tasks import create_task
from app.config import settings
from app.models.task import TaskCreateRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/notion")
async def handle_notion_webhook(
    request: Request,
    notion_signature: str = Header(None, alias="X-Notion-Signature"),
):
    """Receive and verify webhooks from Notion buttons or database triggers."""
    body_bytes = await request.body()

    # Optional signature verification if secret configured
    webhook_secret = getattr(settings, "notion_webhook_secret", None)
    if webhook_secret and notion_signature:
        expected_sig = hmac.new(
            webhook_secret.encode(), body_bytes, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(f"sha256={expected_sig}", notion_signature):
            logger.warning("Invalid Notion webhook signature rejected.")
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload: dict[str, Any] = await request.json()
    logger.info("Received Notion webhook event: %s", payload.get("type", "unknown"))

    # Extract user prompt or trigger context
    data = payload.get("data", {})
    prompt = data.get("prompt") or f"Triggered from Notion: {payload.get('type')}"
    target_id = data.get("page_id") or data.get("database_id")

    task_req = TaskCreateRequest(
        prompt=prompt,
        target_page_ids=[target_id] if target_id else [],
        notify_channels=["notion_comment"],
    )

    created_resp = await create_task(task_req)
    return {"status": "accepted", "task_id": created_resp.task_id}
