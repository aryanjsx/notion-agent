"""Notion tool implementations for the AI agent."""

import logging
from typing import Any

from app.tools.notion.client import get_notion_client
from app.tools.notion.converter import blocks_to_markdown, markdown_to_blocks

logger = logging.getLogger(__name__)


async def notion_search(
    query: str = "",
    filter_type: str | None = None,  # "page" or "database"
    token: str | None = None,
) -> dict[str, Any]:
    """Search Notion workspace for pages or databases matching a query.

    Args:
        query: The search term to match page or database titles.
        filter_type: Optional filter: 'page' or 'database'.
        token: Optional Notion API token override.
    """
    try:
        client = get_notion_client(token)
        filter_dict = (
            {"value": filter_type, "property": "object"} if filter_type else None
        )
        results = await client.search(query=query, filter_dict=filter_dict)

        simplified = []
        for item in results:
            obj_type = item.get("object")
            item_id = str(item.get("id", ""))
            url = item.get("url") or f"https://notion.so/{item_id.replace('-', '')}"
            title = "Untitled"

            if obj_type == "page":
                props = item.get("properties", {})
                for p in props.values():
                    if p.get("type") == "title" and p.get("title"):
                        title = "".join(
                            t.get("plain_text", "") for t in p.get("title", [])
                        )
                        break
            elif obj_type == "database":
                title_list = item.get("title", [])
                if title_list:
                    title = "".join(t.get("plain_text", "") for t in title_list)

            simplified.append(
                {
                    "id": item_id,
                    "type": obj_type,
                    "title": title,
                    "url": url,
                }
            )

        return {"success": True, "count": len(simplified), "results": simplified}
    except Exception as e:
        logger.exception("Error in notion_search: %s", e)
        return {"success": False, "error": str(e), "results": []}


async def notion_get_page(
    page_id: str,
    token: str | None = None,
) -> dict[str, Any]:
    """Retrieve Notion page metadata, properties, and content converted to clean markdown.

    Args:
        page_id: UUID of the Notion page.
        token: Optional Notion API token override.
    """
    try:
        client = get_notion_client(token)
        page_meta = await client.get_page(page_id=page_id)
        blocks = await client.get_page_blocks(page_id=page_id)
        content_markdown = blocks_to_markdown(blocks)

        # Extract title
        title = "Untitled"
        props = page_meta.get("properties", {})
        for p in props.values():
            if p.get("type") == "title" and p.get("title"):
                title = "".join(t.get("plain_text", "") for t in p.get("title", []))
                break

        return {
            "success": True,
            "id": page_id,
            "title": title,
            "url": page_meta.get("url"),
            "properties": props,
            "content_markdown": content_markdown,
            "block_count": len(blocks),
        }
    except Exception as e:
        logger.exception("Error in notion_get_page: %s", e)
        return {"success": False, "error": str(e)}


async def notion_create_page(
    title: str,
    parent_page_id: str | None = None,
    parent_database_id: str | None = None,
    content_markdown: str | None = None,
    properties: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Create a new page in Notion with title and markdown content.

    Args:
        title: Title of the page.
        parent_page_id: Parent page ID to nest this page under (if creating subpage).
        parent_database_id: Parent database ID (if creating database item).
        content_markdown: Markdown formatted body content.
        properties: Optional additional page properties.
        token: Optional Notion API token override.
    """
    try:
        client = get_notion_client(token)
        if parent_database_id:
            parent: dict[str, Any] = {"database_id": parent_database_id}
            props = properties or {}
            # Ensure title property is set for database item
            props["Name"] = {"title": [{"type": "text", "text": {"content": title}}]}
        elif parent_page_id:
            parent = {"page_id": parent_page_id}
            props = {"title": [{"type": "text", "text": {"content": title}}]}
            if properties:
                props.update(properties)
        else:
            # Workspace root level page
            parent = (
                {"page_id": parent_page_id}
                if parent_page_id
                else {"type": "workspace", "workspace": True}
            )
            props = {"title": [{"type": "text", "text": {"content": title}}]}

        children = markdown_to_blocks(content_markdown) if content_markdown else []
        page = await client.create_page(
            parent=parent, properties=props, children=children
        )

        page_id = str(page.get("id", ""))
        page_url = page.get("url") or f"https://notion.so/{page_id.replace('-', '')}"

        return {
            "success": True,
            "id": page_id,
            "title": title,
            "url": page_url,
            "link": {"title": title, "url": page_url, "id": page_id, "type": "page"},
        }
    except Exception as e:
        logger.exception("Error in notion_create_page: %s", e)
        return {"success": False, "error": str(e)}


async def notion_append_blocks(
    page_id: str,
    markdown: str,
    token: str | None = None,
) -> dict[str, Any]:
    """Append markdown content as Notion blocks to the end of a page.

    Args:
        page_id: UUID of the target page.
        markdown: Markdown text to append.
        token: Optional Notion API token override.
    """
    try:
        client = get_notion_client(token)
        blocks = markdown_to_blocks(markdown)
        if not blocks:
            return {"success": True, "appended_count": 0}

        results = await client.append_blocks(block_id=page_id, children=blocks)
        page = await client.get_page(page_id=page_id)
        page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")

        return {
            "success": True,
            "page_id": page_id,
            "url": page_url,
            "appended_count": len(results),
            "link": {
                "title": "Updated Page",
                "url": page_url,
                "id": page_id,
                "type": "page",
            },
        }
    except Exception as e:
        logger.exception("Error in notion_append_blocks: %s", e)
        return {"success": False, "error": str(e)}


async def notion_update_page(
    page_id: str,
    properties: dict[str, Any],
    token: str | None = None,
) -> dict[str, Any]:
    """Update properties of an existing Notion page.

    Args:
        page_id: UUID of the page to update.
        properties: Properties dictionary to update.
        token: Optional Notion API token override.
    """
    try:
        client = get_notion_client(token)
        page = await client.update_page_properties(
            page_id=page_id, properties=properties
        )
        page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
        return {
            "success": True,
            "page_id": page_id,
            "url": page_url,
            "link": {
                "title": "Updated Properties",
                "url": page_url,
                "id": page_id,
                "type": "page",
            },
        }
    except Exception as e:
        logger.exception("Error in notion_update_page: %s", e)
        return {"success": False, "error": str(e)}


async def notion_create_database(
    parent_page_id: str,
    title: str,
    schema: dict[str, Any],
    token: str | None = None,
) -> dict[str, Any]:
    """Create a new database inside a Notion page with specified schema.

    Args:
        parent_page_id: UUID of the parent page.
        title: Title of the database.
        schema: Notion database property schema mapping column names to property types.
        token: Optional Notion API token override.
    """
    try:
        client = get_notion_client(token)
        parent = {"type": "page_id", "page_id": parent_page_id}

        # Build schema ensuring a title column exists
        props_schema: dict[str, Any] = {}
        has_title = False
        for col_name, col_def in schema.items():
            if isinstance(col_def, str):
                col_type = col_def.lower()
                if col_type == "title":
                    has_title = True
                    props_schema[col_name] = {"title": {}}
                elif col_type in ("rich_text", "text"):
                    props_schema[col_name] = {"rich_text": {}}
                elif col_type == "number":
                    props_schema[col_name] = {"number": {"format": "number"}}
                elif col_type == "select":
                    props_schema[col_name] = {"select": {}}
                elif col_type == "multi_select":
                    props_schema[col_name] = {"multi_select": {}}
                elif col_type == "date":
                    props_schema[col_name] = {"date": {}}
                elif col_type in ("checkbox", "boolean"):
                    props_schema[col_name] = {"checkbox": {}}
                elif col_type == "url":
                    props_schema[col_name] = {"url": {}}
                elif col_type == "email":
                    props_schema[col_name] = {"email": {}}
                elif col_type == "status":
                    props_schema[col_name] = {"status": {}}
                else:
                    props_schema[col_name] = {"rich_text": {}}
            elif isinstance(col_def, dict):
                props_schema[col_name] = col_def
                if "title" in col_def:
                    has_title = True

        if not has_title:
            props_schema["Name"] = {"title": {}}

        db = await client.create_database(
            parent=parent, title=title, properties_schema=props_schema
        )
        db_id = str(db.get("id", ""))
        db_url = db.get("url") or f"https://notion.so/{db_id.replace('-', '')}"

        return {
            "success": True,
            "database_id": db_id,
            "title": title,
            "url": db_url,
            "link": {"title": title, "url": db_url, "id": db_id, "type": "database"},
        }
    except Exception as e:
        logger.exception("Error in notion_create_database: %s", e)
        return {"success": False, "error": str(e)}


async def notion_add_database_row(
    database_id: str,
    properties: dict[str, Any],
    content_markdown: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Add a row to a Notion database.

    Args:
        database_id: UUID of the target database.
        properties: Column values formatted for Notion properties.
        content_markdown: Optional markdown content for the row page body.
        token: Optional Notion API token override.
    """
    try:
        client = get_notion_client(token)
        parent = {"database_id": database_id}

        formatted_props: dict[str, Any] = {}
        for key, val in properties.items():
            if isinstance(val, dict):
                formatted_props[key] = val
            elif isinstance(val, str):
                # Try setting as title or rich text
                if key.lower() in ("name", "title"):
                    formatted_props[key] = {
                        "title": [{"type": "text", "text": {"content": val}}]
                    }
                else:
                    formatted_props[key] = {
                        "rich_text": [{"type": "text", "text": {"content": val}}]
                    }
            elif isinstance(val, bool):
                formatted_props[key] = {"checkbox": val}
            elif isinstance(val, (int, float)):
                formatted_props[key] = {"number": val}
            elif isinstance(val, list):
                # Multiselect list of strings
                formatted_props[key] = {"multi_select": [{"name": str(s)} for s in val]}
            else:
                formatted_props[key] = {
                    "rich_text": [{"type": "text", "text": {"content": str(val)}}]
                }

        children = markdown_to_blocks(content_markdown) if content_markdown else []
        page = await client.create_page(
            parent=parent, properties=formatted_props, children=children
        )
        page_id = str(page.get("id", ""))
        page_url = page.get("url") or f"https://notion.so/{page_id.replace('-', '')}"

        return {
            "success": True,
            "row_id": page_id,
            "url": page_url,
            "link": {
                "title": "Database Row",
                "url": page_url,
                "id": page_id,
                "type": "page",
            },
        }
    except Exception as e:
        logger.exception("Error in notion_add_database_row: %s", e)
        return {"success": False, "error": str(e)}


async def notion_query_database(
    database_id: str,
    filter_dict: dict[str, Any] | None = None,
    sorts: list[dict[str, Any]] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Query rows from a database with filtering and sorting.

    Args:
        database_id: UUID of the database.
        filter_dict: Notion query filter object.
        sorts: List of sort specifications.
        token: Optional Notion API token override.
    """
    try:
        client = get_notion_client(token)
        rows = await client.query_database(
            database_id=database_id, filter_dict=filter_dict, sorts=sorts
        )

        parsed_rows = []
        for r in rows:
            row_id = str(r.get("id", ""))
            row_url = r.get("url") or f"https://notion.so/{row_id.replace('-', '')}"
            props = r.get("properties", {})
            parsed_rows.append(
                {
                    "id": row_id,
                    "url": row_url,
                    "properties": props,
                }
            )

        return {"success": True, "count": len(parsed_rows), "rows": parsed_rows}
    except Exception as e:
        logger.exception("Error in notion_query_database: %s", e)
        return {"success": False, "error": str(e), "rows": []}


async def notion_add_comment(
    page_id: str,
    text: str,
    token: str | None = None,
) -> dict[str, Any]:
    """Add a comment or @mention to a Notion page.

    Args:
        page_id: UUID of the page.
        text: Comment message body.
        token: Optional Notion API token override.
    """
    try:
        client = get_notion_client(token)
        comment = await client.add_comment(page_id=page_id, text=text)
        return {"success": True, "comment_id": comment.get("id")}
    except Exception as e:
        logger.exception("Error in notion_add_comment: %s", e)
        return {"success": False, "error": str(e)}


async def notion_archive_page(
    page_id: str,
    token: str | None = None,
) -> dict[str, Any]:
    """Archive (delete) a page in Notion. DESTRUCTIVE: Requires user confirmation.

    Args:
        page_id: UUID of the page to archive.
        token: Optional Notion API token override.
    """
    try:
        client = get_notion_client(token)
        await client.archive_page(page_id=page_id)
        return {"success": True, "archived_id": page_id}
    except Exception as e:
        logger.exception("Error in notion_archive_page: %s", e)
        return {"success": False, "error": str(e)}
