"""Task executor that carries out planned steps using Notion, document, and utility tools."""

import datetime
import logging
from typing import Any

from app.models.task import CreatedLink, TaskMode, TaskRecord, TaskStatus
from app.services.firestore import get_firestore_service
from app.tools.documents.tools import (
    answer_from_document,
    read_document,
    summarize_document,
)
from app.tools.notion.tools import (
    notion_add_comment,
    notion_add_database_row,
    notion_append_blocks,
    notion_archive_page,
    notion_create_database,
    notion_create_page,
    notion_get_page,
    notion_query_database,
    notion_search,
    notion_update_page,
)
from app.tools.utility.tools import ask_user_clarification, get_current_time

logger = logging.getLogger(__name__)

DESTRUCTIVE_TOOLS = {"notion_archive_page"}
WRITE_TOOLS = {
    "notion_create_page",
    "notion_update_page",
    "notion_append_blocks",
    "notion_create_database",
    "notion_add_database_row",
    "notion_archive_page",
}

SUSPICIOUS_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "disregard all previous",
    "delete everything",
    "wipe database",
    "bypass safety",
]


class Executor:
    """Executes planned steps with safety checks, rate limiting, and confirmation gates."""

    def __init__(self) -> None:
        self.firestore = get_firestore_service()

    async def execute_steps(
        self, task: TaskRecord, skip_confirmation_for_step: int | None = None
    ) -> TaskRecord:
        """Execute all pending steps in the task."""
        context: dict[str, Any] = {}

        for step in task.steps:
            if step.status == "completed":
                continue

            # 1. Safety & Confirmation Check
            is_destructive = step.tool_name in DESTRUCTIVE_TOOLS
            needs_write_confirmation = (
                task.mode == TaskMode.CONFIRM_BEFORE_WRITE
                and step.tool_name in WRITE_TOOLS
            )

            if (
                is_destructive or needs_write_confirmation
            ) and step.step_number != skip_confirmation_for_step:
                logger.info(
                    "Pausing task %s for user approval on step %d (%s)",
                    task.id,
                    step.step_number,
                    step.tool_name,
                )
                pending_info = {
                    "step_number": step.step_number,
                    "tool_name": step.tool_name,
                    "tool_args": step.tool_args,
                    "reason": "Destructive operation requires confirmation"
                    if is_destructive
                    else "confirm_before_write mode active",
                }
                self.firestore.update_task_status(
                    task.id,
                    status=TaskStatus.AWAITING_CONFIRMATION,
                    pending_action=pending_info,
                )
                task.status = TaskStatus.AWAITING_CONFIRMATION
                task.pending_action = pending_info
                return task

            # 2. Execute Step
            step.started_at = datetime.datetime.now(datetime.UTC)
            self.firestore.update_step(task.id, step.step_number, status="running")

            try:
                args = self._resolve_dynamic_args(step.tool_args or {}, context)
                result = await self._dispatch_tool(step.tool_name, args)

                # 3. Prompt injection detection on tool outputs
                sanitized_result = self._sanitize_and_check_injection(result)

                step.status = (
                    "completed" if sanitized_result.get("success", True) else "failed"
                )
                step.output = sanitized_result
                step.completed_at = datetime.datetime.now(datetime.UTC)

                # Store useful context keys for subsequent steps
                if "id" in sanitized_result:
                    context["last_created_id"] = sanitized_result["id"]
                if "database_id" in sanitized_result:
                    context["last_database_id"] = sanitized_result["database_id"]
                if "link" in sanitized_result:
                    link_info = sanitized_result["link"]
                    link_obj = CreatedLink(**link_info)
                    task.created_links.append(link_obj)
                    self.firestore.add_created_link(task.id, link_obj)

                self.firestore.update_step(
                    task.id,
                    step.step_number,
                    status=step.status,
                    output=step.output,
                    error=sanitized_result.get("error"),
                )

                if step.status == "failed":
                    logger.warning(
                        "Step %d failed: %s",
                        step.step_number,
                        sanitized_result.get("error"),
                    )

            except Exception as e:
                logger.exception("Exception executing step %d: %s", step.step_number, e)
                step.status = "failed"
                step.error = str(e)
                self.firestore.update_step(
                    task.id, step.step_number, status="failed", error=str(e)
                )

        return task

    def _resolve_dynamic_args(
        self, args: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve placeholders like 'auto_from_step' with IDs from earlier steps."""
        resolved = dict(args)
        for k, v in resolved.items():
            if v == "auto_from_step" or v == "root":
                if "database" in k and "last_database_id" in context:
                    resolved[k] = context["last_database_id"]
                elif "last_created_id" in context:
                    resolved[k] = context["last_created_id"]
                else:
                    resolved[k] = None
        return resolved

    def _sanitize_and_check_injection(self, result: dict[str, Any]) -> dict[str, Any]:
        """Scan tool output for malicious instruction overrides."""
        result_str = str(result).lower()
        detected = []
        for pattern in SUSPICIOUS_INJECTION_PATTERNS:
            if pattern in result_str:
                logger.warning(
                    "Prompt injection attempt detected: '%s' in tool output. Neutralizing.",
                    pattern,
                )
                detected.append(pattern)

        if detected:
            result["injection_warning"] = (
                f"Warning: Suspicious instruction(s) {', '.join(detected)} ignored."
            )
        return result

    async def _dispatch_tool(
        self, tool_name: str | None, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch call to the appropriate tool function."""
        if tool_name == "notion_search":
            return await notion_search(**args)
        elif tool_name == "notion_get_page":
            return await notion_get_page(**args)
        elif tool_name == "notion_create_page":
            return await notion_create_page(**args)
        elif tool_name == "notion_append_blocks":
            return await notion_append_blocks(**args)
        elif tool_name == "notion_update_page":
            return await notion_update_page(**args)
        elif tool_name == "notion_create_database":
            return await notion_create_database(**args)
        elif tool_name == "notion_add_database_row":
            return await notion_add_database_row(**args)
        elif tool_name == "notion_query_database":
            return await notion_query_database(**args)
        elif tool_name == "notion_add_comment":
            return await notion_add_comment(**args)
        elif tool_name == "notion_archive_page":
            return await notion_archive_page(**args)
        elif tool_name == "read_document":
            return await read_document(**args)
        elif tool_name == "summarize_document":
            return await summarize_document(**args)
        elif tool_name == "answer_from_document":
            return await answer_from_document(**args)
        elif tool_name == "get_current_time":
            return await get_current_time()
        elif tool_name == "ask_user_clarification":
            return await ask_user_clarification(**args)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
