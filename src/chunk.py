"""
chunk.py
========
Splits extracted note text into overlapping chunks and writes:
  notes/processed/chunks.json   — consumed by generate_quiz.py via utils.py
  notes/processed/sources.json  — unique source metadata

chunks.json format:
    [{"chunk_id": int, "doc_id": int, "source_file": str, "source_type": str,
      "page": int, "text": str, "char_start": int, "char_end": int}, ...]

sources.json format:
    [{"title": str, "type": str}, ...]

Run after ingest.py:
    python -m src.ingest
    python -m src.chunk
"""

import json
from pathlib import Path

PROCESSED_DIR = Path(__file__).parent.parent / "notes" / "processed"

CHUNK_SIZE = 900   # characters per chunk
OVERLAP    = 150   # overlap between consecutive chunks


def _split_text(text: str, chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    """Return (start, end) character ranges for overlapping chunks of text."""
    ranges = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        ranges.append((start, end))
        if end == len(text):
            break
        start = end - overlap
    return ranges


def chunk_notes(
    processed_dir: str | Path = PROCESSED_DIR,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP,
) -> None:
    """
    Read extracted_text.json, chunk each page, and write chunks.json + sources.json.
    Raises FileNotFoundError if ingest.py hasn't been run yet.
    """
    processed_dir  = Path(processed_dir)
    extracted_path = processed_dir / "extracted_text.json"

    if not extracted_path.exists():
        raise FileNotFoundError(
            f"extracted_text.json not found at {extracted_path}\n"
            "Run  python -m src.ingest  first."
        )

    pages = json.loads(extracted_path.read_text(encoding="utf-8"))

    # One source entry per unique file (not per page)
    seen: dict[str, dict] = {}
    for page in pages:
        fname = page["source_file"]
        if fname not in seen:
            seen[fname] = {"title": fname, "type": page.get("source_type", "unknown")}
    sources = list(seen.values())

    chunks = []
    chunk_id = 0
    for doc_id, page in enumerate(pages):
        text = page.get("text", "").strip()
        if not text:
            continue

        for start, end in _split_text(text, chunk_size, overlap):
            chunks.append({
                "chunk_id":    chunk_id,
                "doc_id":      doc_id,
                "source_file": page["source_file"],
                "source_type": page.get("source_type", "unknown"),
                "page":        page.get("page", 1),
                "text":        text[start:end],
                "char_start":  start,
                "char_end":    end,
                # utils.py reads the "source" key — keep it compatible
                "source":      page["source_file"],
            })
            chunk_id += 1

    (processed_dir / "chunks.json").write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (processed_dir / "sources.json").write_text(
        json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Wrote {len(chunks)} chunks from {len(pages)} page(s) across {len(sources)} source(s)")
    print(f"  -> {processed_dir / 'chunks.json'}")
    print(f"  -> {processed_dir / 'sources.json'}")


if __name__ == "__main__":
    chunk_notes()
