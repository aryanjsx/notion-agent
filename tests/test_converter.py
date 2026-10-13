"""Tests for Markdown <-> Notion Blocks converter."""

from app.tools.notion.converter import (
    blocks_to_markdown,
    chunk_blocks,
    markdown_to_blocks,
)


def test_headings_conversion():
    md = "# Heading One\n\n## Heading Two\n\n### Heading Three"
    blocks = markdown_to_blocks(md)
    assert len(blocks) == 3
    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Heading One"
    assert blocks[1]["type"] == "heading_2"
    assert blocks[2]["type"] == "heading_3"

    # Reverse
    converted_md = blocks_to_markdown(blocks)
    assert "# Heading One" in converted_md
    assert "## Heading Two" in converted_md
    assert "### Heading Three" in converted_md


def test_todo_and_lists_conversion():
    md = "- [ ] Incomplete task\n- [x] Completed task\n- Regular bullet\n1. Numbered item"
    blocks = markdown_to_blocks(md)
    assert len(blocks) == 4
    assert blocks[0]["type"] == "to_do"
    assert blocks[0]["to_do"]["checked"] is False
    assert blocks[1]["type"] == "to_do"
    assert blocks[1]["to_do"]["checked"] is True
    assert blocks[2]["type"] == "bulleted_list_item"
    assert blocks[3]["type"] == "numbered_list_item"

    rev_md = blocks_to_markdown(blocks)
    assert "- [ ] Incomplete task" in rev_md
    assert "- [x] Completed task" in rev_md
    assert "- Regular bullet" in rev_md
    assert "1. Numbered item" in rev_md


def test_code_block_and_callout():
    md = "```python\ndef test():\n    return True\n```\n\n> [!NOTE] This is important"
    blocks = markdown_to_blocks(md)
    assert len(blocks) == 2
    assert blocks[0]["type"] == "code"
    assert blocks[0]["code"]["language"] == "python"
    assert blocks[1]["type"] == "callout"

    rev_md = blocks_to_markdown(blocks)
    assert "```python" in rev_md
    assert "> 💡 [NOTE] This is important" in rev_md


def test_character_limit_chunking():
    # String longer than 2000 chars should be split into multiple rich_text items
    long_text = "A" * 3500
    blocks = markdown_to_blocks(long_text)
    assert len(blocks) == 1
    rich_text = blocks[0]["paragraph"]["rich_text"]
    assert len(rich_text) == 2
    assert len(rich_text[0]["text"]["content"]) == 2000
    assert len(rich_text[1]["text"]["content"]) == 1500


def test_chunk_blocks_batches():
    dummy_blocks = [{"object": "block", "type": "paragraph"}] * 250
    chunks = list(chunk_blocks(dummy_blocks, chunk_size=100))
    assert len(chunks) == 3
    assert len(chunks[0]) == 100
    assert len(chunks[1]) == 100
    assert len(chunks[2]) == 50
