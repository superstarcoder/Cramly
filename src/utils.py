"""utils.py — helpers for loading and combining processed note data."""

import json
from pathlib import Path

NOTES_DIR              = Path(__file__).parent.parent / "notes"
PROCESSED_DIR          = NOTES_DIR / "processed"
HW_PROCESSED_DIR       = NOTES_DIR / "handwritten" / "processed"
MAX_NOTES_CHARS        = 50_000

_REGULAR_CHUNKS_PATH     = PROCESSED_DIR     / "chunks.json"
_HANDWRITTEN_CHUNKS_PATH = HW_PROCESSED_DIR  / "handwritten_chunks.json"


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


def load_all_note_chunks(
    regular_chunks_path: Path = _REGULAR_CHUNKS_PATH,
    handwritten_chunks_path: Path = _HANDWRITTEN_CHUNKS_PATH,
) -> list[dict]:
    """
    Load and combine regular chunks and handwritten chunks into one list.

    Stamps each chunk with "chunk_type": "regular" or "handwritten" if missing.
    Silently skips files that are missing or contain invalid JSON.
    Returns [] if neither file is found.
    """
    all_chunks = []

    for path, chunk_type in [
        (Path(regular_chunks_path),     "regular"),
        (Path(handwritten_chunks_path), "handwritten"),
    ]:
        if not path.exists():
            continue
        try:
            chunks = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(chunks, list):
                print(f"Warning: {path.name} is not a JSON array — skipping.")
                continue
            for c in chunks:
                c.setdefault("chunk_type", chunk_type)
            all_chunks.extend(chunks)
            print(f"Loaded {len(chunks)} {chunk_type} chunks from {path.name}")
        except json.JSONDecodeError as e:
            print(f"Warning: could not parse {path.name}: {e}")

    if not all_chunks:
        print("Warning: no note chunks found — run the notes pipeline first.")

    return all_chunks


def chunks_to_sources(chunks: list[dict]) -> list[dict]:
    """
    Extract a deduplicated source list from a mixed chunk list.
    Returns dicts in the shape the quiz frontend expects:
        [{"title": str, "type": str, "url": str}, ...]
    """
    seen: set[tuple] = set()
    sources = []
    for c in chunks:
        if c.get("chunk_type") == "handwritten":
            title = (c.get("citation") or {}).get("source_file") or c.get("source_file", "Unknown")
            kind  = "handwritten"
        else:
            title = c.get("source") or c.get("source_file", "Unknown")
            kind  = c.get("source_type", "notes")

        key = (title, kind)
        if key not in seen:
            seen.add(key)
            sources.append({"title": title, "type": kind, "url": ""})

    return sources


def chunks_to_text(chunks: list[dict], max_chars: int = MAX_NOTES_CHARS) -> str:
    """Concatenate chunk texts into a single string, truncated to max_chars."""
    text = "\n\n".join(c.get("text", "") for c in chunks)
    return text[:max_chars] if len(text) > max_chars else text
