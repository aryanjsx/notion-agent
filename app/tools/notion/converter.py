"""Markdown <-> Notion Blocks converter with chunking and character limit handling."""

import re
from collections.abc import Generator
from typing import Any

MAX_RICH_TEXT_LENGTH = 2000
MAX_BLOCKS_PER_REQUEST = 100


def _text_to_rich_text(text: str) -> list[dict[str, Any]]:
    """Split text into rich_text array respecting the 2000-character limit."""
    if not text:
        return []
    chunks = []
    # Split string by 2000 characters
    for i in range(0, len(text), MAX_RICH_TEXT_LENGTH):
        chunk = text[i : i + MAX_RICH_TEXT_LENGTH]
        chunks.append(
            {
                "type": "text",
                "text": {"content": chunk},
                "plain_text": chunk,
            }
        )
    return chunks


def _extract_rich_text(rich_text_list: list[dict[str, Any]]) -> str:
    """Extract plain text from a Notion rich_text list."""
    if not rich_text_list:
        return ""
    return "".join(
        item.get("plain_text", item.get("text", {}).get("content", ""))
        for item in rich_text_list
    )


def markdown_to_blocks(markdown_text: str) -> list[dict[str, Any]]:
    """Convert a markdown string into a list of Notion block objects."""
    if not markdown_text:
        return []

    lines = markdown_text.splitlines()
    blocks: list[dict[str, Any]] = []

    in_code_block = False
    code_lang = "plain text"
    code_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Handle code blocks
        if stripped.startswith("```"):
            if not in_code_block:
                in_code_block = True
                lang = stripped[3:].strip()
                code_lang = lang if lang else "plain text"
                code_lines = []
                continue
            else:
                in_code_block = False
                code_content = "\n".join(code_lines)
                blocks.append(
                    {
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": _text_to_rich_text(code_content),
                            "language": code_lang.lower(),
                        },
                    }
                )
                code_lines = []
                continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Skip empty lines
        if not stripped:
            continue

        # Divider
        if stripped in ("---", "***", "___"):
            blocks.append(
                {
                    "object": "block",
                    "type": "divider",
                    "divider": {},
                }
            )
            continue

        # Headings
        if stripped.startswith("### "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": _text_to_rich_text(stripped[4:].strip())
                    },
                }
            )
            continue
        elif stripped.startswith("## "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": _text_to_rich_text(stripped[3:].strip())
                    },
                }
            )
            continue
        elif stripped.startswith("# "):
            blocks.append(
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": _text_to_rich_text(stripped[2:].strip())
                    },
                }
            )
            continue

        # To-Do items
        todo_match = re.match(r"^-\s*\[([ xX])\]\s*(.*)$", stripped)
        if todo_match:
            checked = todo_match.group(1).lower() == "x"
            todo_text = todo_match.group(2).strip()
            blocks.append(
                {
                    "object": "block",
                    "type": "to_do",
                    "to_do": {
                        "rich_text": _text_to_rich_text(todo_text),
                        "checked": checked,
                    },
                }
            )
            continue

        # Bulleted List
        if stripped.startswith(("- ", "* ", "+ ")):
            item_text = stripped[2:].strip()
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": _text_to_rich_text(item_text)},
                }
            )
            continue

        # Numbered List
        numbered_match = re.match(r"^\d+\.\s*(.*)$", stripped)
        if numbered_match:
            item_text = numbered_match.group(1).strip()
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": _text_to_rich_text(item_text)},
                }
            )
            continue

        # Callout (e.g. > [!NOTE] or > 💡)
        callout_match = re.match(
            r"^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$",
            stripped,
            re.IGNORECASE,
        )
        if callout_match:
            callout_text = (
                f"[{callout_match.group(1).upper()}] {callout_match.group(2).strip()}"
            )
            blocks.append(
                {
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": _text_to_rich_text(callout_text),
                        "icon": {"type": "emoji", "emoji": "💡"},
                    },
                }
            )
            continue

        # Quote
        if stripped.startswith("> "):
            blocks.append(
                {
                    "object": "block",
                    "type": "quote",
                    "quote": {"rich_text": _text_to_rich_text(stripped[2:].strip())},
                }
            )
            continue

        # Default: Paragraph
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": _text_to_rich_text(stripped)},
            }
        )

    # Catch unclosed code block if any
    if in_code_block and code_lines:
        blocks.append(
            {
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": _text_to_rich_text("\n".join(code_lines)),
                    "language": code_lang.lower(),
                },
            }
        )

    return blocks


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """Convert Notion block objects into clean Markdown text."""
    md_lines: list[str] = []

    for block in blocks:
        btype = block.get("type", "")
        bdata = block.get(btype, {})

        if btype == "paragraph":
            text = _extract_rich_text(bdata.get("rich_text", []))
            md_lines.append(text)
        elif btype == "heading_1":
            text = _extract_rich_text(bdata.get("rich_text", []))
            md_lines.append(f"# {text}")
        elif btype == "heading_2":
            text = _extract_rich_text(bdata.get("rich_text", []))
            md_lines.append(f"## {text}")
        elif btype == "heading_3":
            text = _extract_rich_text(bdata.get("rich_text", []))
            md_lines.append(f"### {text}")
        elif btype == "bulleted_list_item":
            text = _extract_rich_text(bdata.get("rich_text", []))
            md_lines.append(f"- {text}")
        elif btype == "numbered_list_item":
            text = _extract_rich_text(bdata.get("rich_text", []))
            md_lines.append(f"1. {text}")
        elif btype == "to_do":
            checked = bdata.get("checked", False)
            text = _extract_rich_text(bdata.get("rich_text", []))
            box = "[x]" if checked else "[ ]"
            md_lines.append(f"- {box} {text}")
        elif btype == "quote":
            text = _extract_rich_text(bdata.get("rich_text", []))
            md_lines.append(f"> {text}")
        elif btype == "callout":
            text = _extract_rich_text(bdata.get("rich_text", []))
            md_lines.append(f"> 💡 {text}")
        elif btype == "code":
            lang = bdata.get("language", "")
            text = _extract_rich_text(bdata.get("rich_text", []))
            md_lines.append(f"```{lang}\n{text}\n```")
        elif btype == "divider":
            md_lines.append("---")
        else:
            # Fallback for unsupported or custom blocks
            if "rich_text" in bdata:
                text = _extract_rich_text(bdata["rich_text"])
                if text:
                    md_lines.append(text)

    return "\n\n".join(md_lines)


def chunk_blocks(
    blocks: list[dict[str, Any]], chunk_size: int = MAX_BLOCKS_PER_REQUEST
) -> Generator[list[dict[str, Any]], None, None]:
    """Yield blocks in chunks respecting Notion's maximum 100 blocks per request."""
    for i in range(0, len(blocks), chunk_size):
        yield blocks[i : i + chunk_size]
