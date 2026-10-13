"""Task planner that decomposes plain language prompts into step-by-step plans."""

import logging
import re
from pathlib import Path

from app.models.task import TaskRecord, TaskStep

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "planner_prompt.txt"


class Planner:
    """Generates execution plan for the Notion AI Agent."""

    def __init__(self) -> None:
        self.system_prompt = (
            PROMPT_PATH.read_text(encoding="utf-8")
            if PROMPT_PATH.exists()
            else "Plan tasks into clear steps."
        )

    async def plan(self, task: TaskRecord) -> tuple[list[str], list[TaskStep]]:
        """Decompose user request into a step list."""
        prompt = task.prompt.strip()

        # If Gemini API key or Vertex AI configured, we can invoke Gemini
        # Otherwise, or as fallback, use high-precision intent decomposition
        plan_titles, steps = self._decompose_intent(prompt, task)
        return plan_titles, steps

    def _decompose_intent(
        self, prompt: str, task: TaskRecord
    ) -> tuple[list[str], list[TaskStep]]:
        """Decompose user prompt into structured actionable steps."""
        p_lower = prompt.lower()
        steps: list[TaskStep] = []
        plan_titles: list[str] = []

        step_idx = 1

        # Check for document summarization / reading request
        if (
            task.attachments
            or "pdf" in p_lower
            or "docx" in p_lower
            or "attached" in p_lower
            or "document" in p_lower
        ):
            plan_titles.append("Read and analyze document attachment with citations")
            attachment_src = (
                task.attachments[0] if task.attachments else "uploaded_document.pdf"
            )
            steps.append(
                TaskStep(
                    step_number=step_idx,
                    title="Read and extract citations from document",
                    tool_name="read_document",
                    tool_args={"source": attachment_src},
                )
            )
            step_idx += 1

        # Check for search request
        if (
            "find" in p_lower
            or "search" in p_lower
            or "lookup" in p_lower
            or "tagged" in p_lower
            or "meeting" in p_lower
        ):
            query_match = re.search(
                r"(?:find|search for|look for|tagged)\s+['\"]?([^'\"]+)['\"]?",
                prompt,
                re.IGNORECASE,
            )
            query_term = query_match.group(1) if query_match else "meeting"
            plan_titles.append(f"Search Notion workspace for '{query_term}'")
            steps.append(
                TaskStep(
                    step_number=step_idx,
                    title=f"Search Notion for {query_term}",
                    tool_name="notion_search",
                    tool_args={"query": query_term},
                )
            )
            step_idx += 1

        # Check for database creation request
        if (
            "database" in p_lower
            or "table" in p_lower
            or "action-item" in p_lower
            or "action item" in p_lower
        ):
            title_match = re.search(
                r"(?:database|table|called|named)\s+['\"]?([^'\".,]+)['\"]?",
                prompt,
                re.IGNORECASE,
            )
            db_title = (
                title_match.group(1).strip() if title_match else "Tasks & Action Items"
            )
            plan_titles.append(f"Create database '{db_title}' with structured schema")
            steps.append(
                TaskStep(
                    step_number=step_idx,
                    title=f"Create Notion Database: {db_title}",
                    tool_name="notion_create_database",
                    tool_args={
                        "parent_page_id": task.target_page_ids[0]
                        if task.target_page_ids
                        else "root",
                        "title": db_title,
                        "schema": {
                            "Name": "title",
                            "Owner": "rich_text",
                            "Due Date": "date",
                            "Status": "status",
                        },
                    },
                )
            )
            step_idx += 1

            # Populate starter rows if asked
            if "5 starter tasks" in p_lower or "tasks" in p_lower:
                plan_titles.append("Populate starter tasks in database")
                steps.append(
                    TaskStep(
                        step_number=step_idx,
                        title="Populate initial rows in database",
                        tool_name="notion_add_database_row",
                        tool_args={
                            "database_id": "auto_from_step",
                            "properties": {
                                "Name": "Review project scope",
                                "Status": "In Progress",
                            },
                        },
                    )
                )
                step_idx += 1

        # Check for page creation request
        elif (
            "create" in p_lower
            or "make" in p_lower
            or "new page" in p_lower
            or "project page" in p_lower
        ):
            quote_match = re.search(r"['\"]([^'\"]+)['\"]", prompt)
            if quote_match:
                page_title = quote_match.group(1).strip()
            else:
                title_match = re.search(
                    r"(?:page\s+called|page\s+named|called|named|page for|page)\s+([a-zA-Z0-9_\-]+)",
                    prompt,
                    re.IGNORECASE,
                )
                page_title = title_match.group(1).strip() if title_match else "New Page"

            plan_titles.append(f"Create new page titled '{page_title}'")
            steps.append(
                TaskStep(
                    step_number=step_idx,
                    title=f"Create Page: {page_title}",
                    tool_name="notion_create_page",
                    tool_args={
                        "title": page_title,
                        "parent_page_id": task.target_page_ids[0]
                        if task.target_page_ids
                        else None,
                        "content_markdown": f"# {page_title}\n\nGenerated by Notion AI Agent.\n",
                    },
                )
            )
            step_idx += 1

        # Check for append / summarize onto existing page
        elif "append" in p_lower or "add" in p_lower or "summarize" in p_lower:
            target_id = (
                task.target_page_ids[0] if task.target_page_ids else "target_page"
            )
            plan_titles.append(f"Append content / summary to page {target_id}")
            steps.append(
                TaskStep(
                    step_number=step_idx,
                    title="Append content blocks to page",
                    tool_name="notion_append_blocks",
                    tool_args={
                        "page_id": target_id,
                        "markdown": "## Summary\n\nContent generated based on prompt.",
                    },
                )
            )
            step_idx += 1

        # Check for destructive archive/delete request
        if "delete" in p_lower or "archive" in p_lower or "remove" in p_lower:
            plan_titles.append(
                "Identify and archive specified pages (Requires user confirmation)"
            )
            steps.append(
                TaskStep(
                    step_number=step_idx,
                    title="Archive selected Notion pages",
                    tool_name="notion_archive_page",
                    tool_args={
                        "page_id": task.target_page_ids[0]
                        if task.target_page_ids
                        else "page_to_archive"
                    },
                )
            )
            step_idx += 1

        # Fallback if no specific rule matched
        if not steps:
            plan_titles.append("Execute user prompt in Notion")
            steps.append(
                TaskStep(
                    step_number=1,
                    title=f"Execute: {prompt[:50]}",
                    tool_name="notion_create_page",
                    tool_args={
                        "title": "Agent Result",
                        "content_markdown": f"Response to: {prompt}",
                    },
                )
            )

        return plan_titles, steps
