"""Tests for Notion tools with mocked NotionClientWrapper."""

from unittest.mock import AsyncMock, patch

import pytest

from app.tools.notion.tools import (
    notion_archive_page,
    notion_create_database,
    notion_create_page,
    notion_search,
)


@pytest.mark.asyncio
async def test_notion_search_mock():
    mock_results = [
        {
            "id": "11111111-2222-3333-4444-555555555555",
            "object": "page",
            "url": "https://notion.so/test-page",
            "properties": {
                "Title": {
                    "type": "title",
                    "title": [{"plain_text": "Meeting Notes"}],
                }
            },
        }
    ]
    with patch("app.tools.notion.tools.get_notion_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.search.return_value = mock_results
        mock_get_client.return_value = mock_client

        res = await notion_search(query="Meeting")
        assert res["success"] is True
        assert res["count"] == 1
        assert res["results"][0]["title"] == "Meeting Notes"


@pytest.mark.asyncio
async def test_notion_create_page_mock():
    with patch("app.tools.notion.tools.get_notion_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.create_page.return_value = {
            "id": "page-12345",
            "url": "https://notion.so/page-12345",
        }
        mock_get_client.return_value = mock_client

        res = await notion_create_page(
            title="Q4 Launch Plan",
            content_markdown="# Overview\nStarter text.",
        )
        assert res["success"] is True
        assert res["id"] == "page-12345"
        assert res["title"] == "Q4 Launch Plan"
        assert res["link"]["type"] == "page"


@pytest.mark.asyncio
async def test_notion_create_database_mock():
    with patch("app.tools.notion.tools.get_notion_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.create_database.return_value = {
            "id": "db-67890",
            "url": "https://notion.so/db-67890",
        }
        mock_get_client.return_value = mock_client

        schema = {
            "Task": "title",
            "Assignee": "rich_text",
            "Status": "status",
        }
        res = await notion_create_database(
            parent_page_id="page-12345",
            title="Action Items",
            schema=schema,
        )
        assert res["success"] is True
        assert res["database_id"] == "db-67890"
        assert res["title"] == "Action Items"


@pytest.mark.asyncio
async def test_notion_archive_page_mock():
    with patch("app.tools.notion.tools.get_notion_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.archive_page.return_value = {}
        mock_get_client.return_value = mock_client

        res = await notion_archive_page(page_id="page-to-delete")
        assert res["success"] is True
        assert res["archived_id"] == "page-to-delete"
