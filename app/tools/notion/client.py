"""Notion API client wrapper with rate limiting, retries, and error handling."""

import asyncio
import logging
from typing import Any

from notion_client import APIResponseError, AsyncClient

from app.config import settings
from app.tools.notion.rate_limiter import notion_rate_limiter

logger = logging.getLogger(__name__)


class NotionClientWrapper:
    """Wrapper around official AsyncClient with rate limiting and exponential backoff."""

    def __init__(self, auth_token: str | None = None) -> None:
        token = auth_token or settings.notion_api_key
        self.client: AsyncClient | None = AsyncClient(auth=token) if token else None

    def _ensure_client(self) -> AsyncClient:
        if not self.client:
            token = settings.notion_api_key
            if not token:
                raise ValueError(
                    "Notion API key/token is missing. Set NOTION_API_KEY in .env or provide an integration token."
                )
            self.client = AsyncClient(auth=token)
        return self.client

    async def _execute_with_retry(self, api_func, *args, **kwargs) -> Any:
        """Execute a Notion API call with rate limiting and exponential backoff on 429/5xx."""
        max_retries = 5
        base_delay = 1.0

        for attempt in range(max_retries):
            # Wait for rate limiter token
            await notion_rate_limiter.acquire()

            try:
                return await api_func(*args, **kwargs)
            except APIResponseError as err:
                status = getattr(err, "status", None)
                if status == 429 or (status and status >= 500):
                    delay = base_delay * (2**attempt)
                    retry_after = getattr(err, "headers", {}).get("Retry-After")
                    if retry_after:
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            pass
                    logger.warning(
                        "Notion API returned status %s. Retrying in %.2f seconds (attempt %d/%d)...",
                        status,
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Notion API error: %s (code: %s)",
                        str(err),
                        getattr(err, "code", ""),
                    )
                    raise
            except Exception as ex:
                if attempt == max_retries - 1:
                    raise
                logger.warning(
                    "Unexpected error communicating with Notion: %s. Retrying...", ex
                )
                await asyncio.sleep(base_delay * (2**attempt))

        raise RuntimeError(
            f"Exceeded maximum retries ({max_retries}) for Notion API call."
        )

    async def search(
        self, query: str = "", filter_dict: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Search Notion workspace pages and databases."""
        client = self._ensure_client()
        kwargs: dict[str, Any] = {"query": query}
        if filter_dict:
            kwargs["filter"] = filter_dict

        resp = await self._execute_with_retry(client.search, **kwargs)
        return resp.get("results", [])

    async def get_page(self, page_id: str) -> dict[str, Any]:
        """Fetch Notion page metadata and properties."""
        client = self._ensure_client()
        return await self._execute_with_retry(client.pages.retrieve, page_id=page_id)

    async def get_page_blocks(self, page_id: str) -> list[dict[str, Any]]:
        """Fetch all blocks on a page with pagination."""
        client = self._ensure_client()
        all_blocks: list[dict[str, Any]] = []
        has_more = True
        start_cursor = None

        while has_more:
            kwargs: dict[str, Any] = {"block_id": page_id}
            if start_cursor:
                kwargs["start_cursor"] = start_cursor

            resp = await self._execute_with_retry(client.blocks.children.list, **kwargs)
            results = resp.get("results", [])
            all_blocks.extend(results)
            has_more = resp.get("has_more", False)
            start_cursor = resp.get("next_cursor")

        return all_blocks

    async def create_page(
        self,
        parent: dict[str, Any],
        properties: dict[str, Any],
        children: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a new page in Notion."""
        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "parent": parent,
            "properties": properties,
        }
        if children:
            # First batch up to 100 blocks
            kwargs["children"] = children[:100]

        page = await self._execute_with_retry(client.pages.create, **kwargs)

        # If there are remaining blocks beyond 100, append them in batches
        if children and len(children) > 100:
            remaining = children[100:]
            for i in range(0, len(remaining), 100):
                batch = remaining[i : i + 100]
                await self.append_blocks(page["id"], batch)

        return page

    async def update_page_properties(
        self, page_id: str, properties: dict[str, Any]
    ) -> dict[str, Any]:
        """Update properties of an existing Notion page."""
        client = self._ensure_client()
        return await self._execute_with_retry(
            client.pages.update, page_id=page_id, properties=properties
        )

    async def append_blocks(
        self, block_id: str, children: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Append children blocks to a block or page in chunks of 100."""
        client = self._ensure_client()
        appended: list[dict[str, Any]] = []
        for i in range(0, len(children), 100):
            batch = children[i : i + 100]
            resp = await self._execute_with_retry(
                client.blocks.children.append, block_id=block_id, children=batch
            )
            appended.extend(resp.get("results", []))
        return appended

    async def update_block(
        self, block_id: str, block_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing Notion block."""
        client = self._ensure_client()
        return await self._execute_with_retry(
            client.blocks.update, block_id=block_id, **block_data
        )

    async def query_database(
        self,
        database_id: str,
        filter_dict: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Query rows from a Notion database with pagination."""
        client = self._ensure_client()
        results: list[dict[str, Any]] = []
        has_more = True
        start_cursor = None

        while has_more:
            kwargs: dict[str, Any] = {
                "database_id": database_id,
                "page_size": page_size,
            }
            if filter_dict:
                kwargs["filter"] = filter_dict
            if sorts:
                kwargs["sorts"] = sorts
            if start_cursor:
                kwargs["start_cursor"] = start_cursor

            resp = await self._execute_with_retry(
                client.databases.query, **kwargs  # type: ignore[attr-defined]
            )
            results.extend(resp.get("results", []))
            has_more = resp.get("has_more", False)
            start_cursor = resp.get("next_cursor")

        return results

    async def create_database(
        self,
        parent: dict[str, Any],
        title: str,
        properties_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new database with specified schema."""
        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "parent": parent,
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties_schema,
        }
        return await self._execute_with_retry(client.databases.create, **kwargs)

    async def add_comment(self, page_id: str, text: str) -> dict[str, Any]:
        """Add a comment to a Notion page."""
        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "parent": {"page_id": page_id},
            "rich_text": [{"type": "text", "text": {"content": text}}],
        }
        return await self._execute_with_retry(client.comments.create, **kwargs)

    async def archive_page(self, page_id: str) -> dict[str, Any]:
        """Archive (soft-delete) a page in Notion."""
        client = self._ensure_client()
        return await self._execute_with_retry(
            client.pages.update, page_id=page_id, archived=True
        )


_notion_client_instance: NotionClientWrapper | None = None


def get_notion_client(token: str | None = None) -> NotionClientWrapper:
    global _notion_client_instance
    if token:
        return NotionClientWrapper(auth_token=token)
    if _notion_client_instance is None:
        _notion_client_instance = NotionClientWrapper()
    return _notion_client_instance
