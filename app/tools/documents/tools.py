"""Document analysis tools with citation extraction."""

import logging
from typing import Any

from app.services.storage import get_storage_service
from app.tools.documents.parser import DocumentParser

logger = logging.getLogger(__name__)


async def read_document(source: str) -> dict[str, Any]:
    """Read a document (PDF, DOCX, TXT, CSV) and extract text chunks with page citations.

    Args:
        source: URI or path to the document (e.g. gs://..., local://..., or file path).
    """
    try:
        storage = get_storage_service()
        data = storage.download_bytes(source)
        filename = source.split("/")[-1]

        chunks = DocumentParser.parse(filename, data)
        structured_chunks = []
        full_text_list = []

        for c in chunks:
            citation = (
                f"Page {c.page_number}"
                if c.page_number
                else (c.section_title or f"Section {c.chunk_index + 1}")
            )
            structured_chunks.append(
                {
                    "citation": citation,
                    "text": c.text,
                    "page_number": c.page_number,
                    "section": c.section_title,
                }
            )
            full_text_list.append(f"[{citation}]\n{c.text}")

        full_text = "\n\n".join(full_text_list)
        return {
            "success": True,
            "filename": filename,
            "total_chunks": len(chunks),
            "chunks": structured_chunks[:15],  # preview top 15 chunks
            "full_text_preview": full_text[:4000],
            "total_character_count": len(full_text),
        }
    except Exception as e:
        logger.exception("Error in read_document: %s", e)
        return {"success": False, "error": str(e)}


async def summarize_document(
    source: str,
    focus: str | None = None,
) -> dict[str, Any]:
    """Extract key takeaways and summarize document with page citations.

    Args:
        source: URI or file path to document.
        focus: Specific topic or questions to focus on.
    """
    doc_res = await read_document(source)
    if not doc_res.get("success"):
        return doc_res

    chunks = doc_res.get("chunks", [])
    # Formulate structured summary with citations
    points = []
    for c in chunks:
        citation = c.get("citation", "Doc")
        text_snippet = c.get("text", "").split("\n")[0][:180]
        if text_snippet:
            points.append(f"- ({citation}) {text_snippet}")

    summary_text = "\n".join(points[:10])
    return {
        "success": True,
        "source": source,
        "focus": focus,
        "summary": summary_text,
        "citation_count": len(points),
    }


async def answer_from_document(
    source: str,
    question: str,
) -> dict[str, Any]:
    """Search document chunks and answer a specific question with citations.

    Args:
        source: URI or path to document.
        question: Question to answer from the document.
    """
    doc_res = await read_document(source)
    if not doc_res.get("success"):
        return doc_res

    chunks = doc_res.get("chunks", [])
    query_words = set(question.lower().split())

    # Simple keyword relevance scoring
    scored_chunks = []
    for c in chunks:
        text_lower = c.get("text", "").lower()
        score = sum(1 for w in query_words if w in text_lower)
        if score > 0:
            scored_chunks.append((score, c))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    top_matches = (
        [item[1] for item in scored_chunks[:3]] if scored_chunks else chunks[:2]
    )

    answers = []
    for match in top_matches:
        answers.append(
            {
                "citation": match.get("citation"),
                "relevant_text": match.get("text")[:400],
            }
        )

    return {
        "success": True,
        "question": question,
        "matches": answers,
    }
