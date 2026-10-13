"""Task verifier that validates outputs against user prompt and generates final summary."""

import logging

from app.models.task import TaskRecord, TaskStatus

logger = logging.getLogger(__name__)


class Verifier:
    """Verifies that executed steps satisfied the user's original request."""

    def verify(self, task: TaskRecord) -> tuple[TaskStatus, str, str, str]:
        """Verify task execution and return (status, summary, error_message, suggested_fix)."""
        prompt = task.prompt
        steps = task.steps

        if not steps:
            return (
                TaskStatus.FAILED,
                "No steps were planned or executed.",
                "Empty plan",
                "Try rephrasing your request.",
            )

        failed_steps = [s for s in steps if s.status == "failed"]
        completed_steps = [s for s in steps if s.status == "completed"]

        if failed_steps and not completed_steps:
            err = failed_steps[0].error or "Step failed execution"
            return (
                TaskStatus.FAILED,
                f"Execution failed at step {failed_steps[0].step_number}: {failed_steps[0].title}",
                err,
                "Check Notion API credentials, integration permissions on the target page, or document file format.",
            )

        # Build clean summary
        created_count = len(task.created_links)
        links_preview = ", ".join(
            f"'{link.title}' ({link.type})" for link in task.created_links[:3]
        )

        if failed_steps:
            # Partial success
            summary = (
                f"Task partially succeeded. Completed {len(completed_steps)} of {len(steps)} planned steps. "
                f"Created/modified: {links_preview or 'None'}. "
                f"Step {failed_steps[0].step_number} encountered an error: {failed_steps[0].error}."
            )
            return (
                TaskStatus.FAILED,
                summary,
                failed_steps[0].error or "Partial step failure",
                "Ensure target Notion pages are shared with your Notion integration bot.",
            )

        # Full success
        summary = (
            f'Successfully processed request: "{prompt[:80]}". '
            f"Executed {len(completed_steps)} steps. "
            f"Updated Notion with {created_count} page/database artifact(s): {links_preview}."
        )
        return TaskStatus.SUCCEEDED, summary, "", ""
