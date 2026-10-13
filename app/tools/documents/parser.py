"""Document parsing and chunking for PDF, DOCX, TXT, and CSV."""

import csv
import io
import logging
from dataclasses import dataclass

import docx
from pypdf import PdfReader

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    text: str
    page_number: int | None = None
    section_title: str | None = None
    chunk_index: int = 0


class DocumentParser:
    """Parses various file types into structured text with page/section citations."""

    @staticmethod
    def parse_pdf(data: bytes) -> list[DocumentChunk]:
        """Extract text page by page from PDF bytes."""
        chunks: list[DocumentChunk] = []
        reader = PdfReader(io.BytesIO(data))
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                chunks.append(
                    DocumentChunk(
                        text=text,
                        page_number=idx + 1,
                        chunk_index=len(chunks),
                    )
                )
        return chunks

    @staticmethod
    def parse_docx(data: bytes) -> list[DocumentChunk]:
        """Extract text paragraphs and headings from DOCX bytes."""
        chunks: list[DocumentChunk] = []
        doc = docx.Document(io.BytesIO(data))
        current_heading = "General"
        buffer: list[str] = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            if p.style and p.style.name and p.style.name.startswith("Heading"):
                if buffer:
                    chunks.append(
                        DocumentChunk(
                            text="\n".join(buffer),
                            section_title=current_heading,
                            chunk_index=len(chunks),
                        )
                    )
                    buffer = []
                current_heading = text
            else:
                buffer.append(text)

        if buffer:
            chunks.append(
                DocumentChunk(
                    text="\n".join(buffer),
                    section_title=current_heading,
                    chunk_index=len(chunks),
                )
            )
        return chunks

    @staticmethod
    def parse_txt(data: bytes) -> list[DocumentChunk]:
        """Extract text from plain text or markdown bytes."""
        text = data.decode("utf-8", errors="replace").strip()
        # Split into ~1000 char chunks with paragraph awareness
        paragraphs = text.split("\n\n")
        chunks: list[DocumentChunk] = []
        buffer: list[str] = []
        current_len = 0

        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue
            if current_len + len(p_clean) > 1500 and buffer:
                chunks.append(
                    DocumentChunk(
                        text="\n\n".join(buffer),
                        chunk_index=len(chunks),
                    )
                )
                buffer = [p_clean]
                current_len = len(p_clean)
            else:
                buffer.append(p_clean)
                current_len += len(p_clean)

        if buffer:
            chunks.append(
                DocumentChunk(
                    text="\n\n".join(buffer),
                    chunk_index=len(chunks),
                )
            )
        return chunks

    @staticmethod
    def parse_csv(data: bytes) -> list[DocumentChunk]:
        """Extract tabular data from CSV bytes as markdown tables."""
        text = data.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return []

        header = rows[0]
        md_table_lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(["---"] * len(header)) + " |",
        ]
        for row in rows[1:101]:  # preview up to 100 rows
            md_table_lines.append("| " + " | ".join(row) + " |")

        return [
            DocumentChunk(
                text="\n".join(md_table_lines),
                section_title="CSV Data",
                chunk_index=0,
            )
        ]

    @classmethod
    def parse(cls, filename: str, data: bytes) -> list[DocumentChunk]:
        """Auto-detect format by extension and parse bytes."""
        lower = filename.lower()
        if lower.endswith(".pdf"):
            return cls.parse_pdf(data)
        elif lower.endswith(".docx"):
            return cls.parse_docx(data)
        elif lower.endswith(".csv"):
            return cls.parse_csv(data)
        else:
            return cls.parse_txt(data)
