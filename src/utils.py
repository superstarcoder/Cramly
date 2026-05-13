"""utils.py — helpers for loading and combining processed note data."""

import json
from pathlib import Path

NOTES_DIR = Path(__file__).parent.parent / "notes"
PROCESSED_DIR = NOTES_DIR / "processed"
MAX_NOTES_CHARS = 50_000


def load_chunks(processed_dir: Path = PROCESSED_DIR) -> list[dict]:
    """
    Load chunks from notes/processed/chunks.json.

    Expected format (produced by src/chunk.py):
        [{"text": str, "source": str, "chunk_id": int}, ...]

    Returns [] if the file does not exist yet.
    """
    path = processed_dir / "chunks.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_sources(processed_dir: Path = PROCESSED_DIR) -> list[dict]:
    """
    Load sources from notes/processed/sources.json.

    Expected format (produced by src/chunk.py):
        [{"title": str, "type": str}, ...]

    Returns [] if the file does not exist yet.
    """
    path = processed_dir / "sources.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def chunks_to_text(chunks: list[dict], max_chars: int = MAX_NOTES_CHARS) -> str:
    """Concatenate chunk texts into a single string, truncated to max_chars."""
    text = "\n\n".join(c.get("text", "") for c in chunks)
    return text[:max_chars] if len(text) > max_chars else text
