"""
cite.py
=======
Formats source references from notes/processed/sources.json into
human-readable strings for inclusion in study guides and quizzes.
"""

import json
from pathlib import Path

PROCESSED_DIR = Path(__file__).parent.parent / "notes" / "processed"


def load_sources(processed_dir: Path = PROCESSED_DIR) -> list[dict]:
    path = processed_dir / "sources.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def format_citations(sources: list[dict]) -> str:
    """Return a markdown-formatted references block from a list of source dicts."""
    if not sources:
        return ""

    lines = ["**Sources:**"]
    for i, src in enumerate(sources, start=1):
        title = src.get("title", "Unknown")
        kind  = src.get("type", "file")
        lines.append(f"{i}. {title} *({kind})*")

    return "\n".join(lines)


def citations_for_quiz(sources: list[dict]) -> list[dict]:
    """
    Return sources in the shape expected by the quiz frontend:
    [{"title": str, "type": str, "url": str}, ...]
    """
    return [
        {
            "title": src.get("title", "Unknown"),
            "type":  src.get("type", "notes"),
            "url":   "",
        }
        for src in sources
    ]


def cite_chunk(chunk: dict) -> str:
    """
    Return a short inline citation label for a single chunk.

    Regular:     [chunk_001: lecture.pdf, page 2]
    Handwritten: [hw_chunk_001: Final.pdf, page 4]
    """
    chunk_id = chunk.get("chunk_id", "unknown")
    if chunk.get("chunk_type") == "handwritten":
        citation = chunk.get("citation") or {}
        source   = citation.get("source_file") or chunk.get("source_file", "unknown")
        page     = citation.get("page") or chunk.get("page", "?")
    else:
        source = chunk.get("source") or chunk.get("source_file", "unknown")
        page   = chunk.get("page", "?")
    return f"[{chunk_id}: {source}, page {page}]"
