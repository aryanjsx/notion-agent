"""Utility tools for the agent."""

from datetime import UTC, datetime
from typing import Any


async def get_current_time() -> dict[str, Any]:
    """Return the current ISO timestamp and formatted date/time."""
    now = datetime.now(UTC)
    return {
        "success": True,
        "iso_timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time_utc": now.strftime("%H:%M:%S UTC"),
    }


async def ask_user_clarification(question: str) -> dict[str, Any]:
    """Pause execution and request clarification from the user.

    Args:
        question: The question to ask the user.
    """
    return {
        "success": True,
        "action": "pause_for_clarification",
        "question": question,
    }
