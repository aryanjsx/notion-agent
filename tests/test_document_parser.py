"""Tests for Document Parser and chunking."""

import io

from pypdf import PdfWriter

from app.tools.documents.parser import DocumentParser


def test_parse_txt_and_citations():
    text = "Paragraph 1 content here.\n\nParagraph 2 with key research notes."
    chunks = DocumentParser.parse_txt(text.encode("utf-8"))
    assert len(chunks) >= 1
    assert "Paragraph 1" in chunks[0].text


def test_parse_pdf_pages_and_citations():
    # Generate in-memory PDF with 2 pages using pypdf
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    stream = io.BytesIO()
    writer.write(stream)
    pdf_bytes = stream.getvalue()

    chunks = DocumentParser.parse("test.pdf", pdf_bytes)
    # Blank pages might not have text, but parser shouldn't crash
    assert isinstance(chunks, list)


def test_parse_csv():
    csv_data = b"Name,Role,Status\nAlice,Lead,Active\nBob,Engineer,Active\n"
    chunks = DocumentParser.parse("team.csv", csv_data)
    assert len(chunks) == 1
    assert "| Name | Role | Status |" in chunks[0].text
    assert "| Alice | Lead | Active |" in chunks[0].text
