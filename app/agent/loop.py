"""Agent execution loop coordinating planning, execution, verification, and notification."""

import logging
import time

from app.agent.executor import Executor
from app.agent.planner import Planner
from app.agent.verifier import Verifier
from app.models.task import TaskRecord, TaskStatus
from app.notify.dispatcher import NotificationDispatcher
from app.services.firestore import get_firestore_service

logger = logging.getLogger(__name__)


class AgentLoop:
    """End-to-end agent workflow runner."""

    def __init__(self) -> None:
        self.planner = Planner()
        self.executor = Executor()
        self.verifier = Verifier()
        self.firestore = get_firestore_service()

    async def run(self, task_id: str) -> TaskRecord | None:
        """Execute the full agent lifecycle for a given task ID."""
        task = self.firestore.get_task(task_id)
        if not task:
            logger.error("Task not found for ID: %s", task_id)
            return None

        start_time = time.monotonic()
        logger.info(
            "Starting execution for task %s (prompt: '%s')", task.id, task.prompt[:60]
        )

        try:
            # 1. Planning Phase
            self.firestore.update_task_status(task.id, status=TaskStatus.PLANNING)
            plan_titles, steps = await self.planner.plan(task)
            task.plan = plan_titles
            task.steps = steps
            self.firestore.update_task_status(
                task.id, status=TaskStatus.RUNNING, plan=plan_titles
            )
            for step in steps:
                self.firestore.add_step(task.id, step)

            # 2. Execution Phase
            task = await self.executor.execute_steps(task)

            # If task was paused for human confirmation, stop here
            if task.status == TaskStatus.AWAITING_CONFIRMATION:
                logger.info("Task %s is paused awaiting user confirmation.", task.id)
                # Dispatch notification informing user that approval is required
                await NotificationDispatcher.dispatch_all(task)
                return task

            # 3. Verification Phase
            status, summary, error_msg, suggested_fix = self.verifier.verify(task)
            duration = time.monotonic() - start_time

            updated_task = self.firestore.update_task_status(
                task.id,
                status=status,
                summary=summary,
                error_message=error_msg,
                suggested_fix=suggested_fix,
                duration_seconds=duration,
            )

            # 4. Notification Phase
            final_task = updated_task or task
            await NotificationDispatcher.dispatch_all(final_task)
            final_task = self.firestore.get_task(task.id) or final_task
            logger.info(
                "Task %s completed with status: %s (duration: %.2fs)",
                task.id,
                status.value,
                duration,
            )
            return final_task

        except Exception as e:
            logger.exception("Fatal error in agent loop for task %s: %s", task.id, e)
            duration = time.monotonic() - start_time
            updated_task = self.firestore.update_task_status(
                task.id,
                status=TaskStatus.FAILED,
                error_message=str(e),
                suggested_fix="Review error log and verify service permissions.",
                duration_seconds=duration,
            )
            final_task = updated_task or task
            await NotificationDispatcher.dispatch_all(final_task)
            return final_task

    async def resume_with_confirmation(
        self,
        task_id: str,
        approved: bool,
        feedback: str | None = None,
    ) -> TaskRecord | None:
        """Resume a paused task after human confirmation or rejection."""
        task = self.firestore.get_task(task_id)
        if not task:
            return None

        if task.status != TaskStatus.AWAITING_CONFIRMATION:
            logger.warning(
                "Task %s is not awaiting confirmation (status: %s)",
                task.id,
                task.status,
            )
            return task

        if not approved:
            # User rejected the action
            summary = f"Operation cancelled by user approval rejection. Feedback: {feedback or 'None'}"
            updated = self.firestore.update_task_status(
                task.id,
                status=TaskStatus.CANCELLED,
                summary=summary,
            )
            final_task = updated or task
            await NotificationDispatcher.dispatch_all(final_task)
            return final_task

        # User approved: continue execution
        logger.info(
            "User approved pending action for task %s. Resuming execution...", task.id
        )
        pending_step_num = (
            task.pending_action.get("step_number") if task.pending_action else None
        )

        # Mark pending step as approved and unpause
        self.firestore.update_task_status(
            task.id, status=TaskStatus.RUNNING, pending_action=None
        )
        task.status = TaskStatus.RUNNING

        # Re-run execution for remaining steps
        task = await self.executor.execute_steps(
            task, skip_confirmation_for_step=pending_step_num
        )
        if task.status == TaskStatus.AWAITING_CONFIRMATION:
            return task

        status, summary, error_msg, suggested_fix = self.verifier.verify(task)
        updated_task = self.firestore.update_task_status(
            task.id,
            status=status,
            summary=summary,
            error_message=error_msg,
            suggested_fix=suggested_fix,
        )
        final_task = updated_task or task
        await NotificationDispatcher.dispatch_all(final_task)
        return final_task


_agent_loop_instance: AgentLoop | None = None


def get_agent_loop() -> AgentLoop:
    global _agent_loop_instance
    if _agent_loop_instance is None:
        _agent_loop_instance = AgentLoop()
    return _agent_loop_instance
