"""Tests for Agent Planner."""

import pytest

from app.agent.planner import Planner
from app.models.task import TaskRecord


@pytest.mark.asyncio
async def test_planner_creates_page_plan():
    planner = Planner()
    task = TaskRecord(
        id="t-1",
        prompt="Create a page called 'Q4 Launch Plan' with starter text",
    )
    plan_titles, steps = await planner.plan(task)
    assert len(plan_titles) >= 1
    assert any("Q4 Launch Plan" in t for t in plan_titles)
    assert steps[0].tool_name == "notion_create_page"


@pytest.mark.asyncio
async def test_planner_database_request():
    planner = Planner()
    task = TaskRecord(
        id="t-2",
        prompt="Create a project page for Q4 with a task database and 5 starter tasks",
    )
    _plan_titles, steps = await planner.plan(task)
    tool_names = [s.tool_name for s in steps]
    assert "notion_create_database" in tool_names or "notion_create_page" in tool_names


@pytest.mark.asyncio
async def test_planner_destructive_action():
    planner = Planner()
    task = TaskRecord(
        id="t-3",
        prompt="Delete all my old drafts",
    )
    plan_titles, steps = await planner.plan(task)
    assert any("confirmation" in t.lower() for t in plan_titles)
    assert steps[0].tool_name == "notion_archive_page"
