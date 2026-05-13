"""
chunk.py
========
Abstract:
    Splits ingested note text into overlapping chunks suitable for LLM context
    windows, then writes structured output to notes/processed/. Step 5-6 of
    the pipeline.

Output contract (read by generate_quiz.py via src/utils.py):
    notes/processed/chunks.json  — list of chunk dicts
    notes/processed/sources.json — list of source dicts

chunks.json format:
    [{"text": str, "source": str, "chunk_id": int}, ...]

sources.json format:
    [{"title": str, "type": str}, ...]

TODO (groupmate): implement chunking strategy (chunk size, overlap, etc.).
"""

import json
from pathlib import Path

PROCESSED_DIR = Path(__file__).parent.parent / "notes" / "processed"


def chunk_and_save(notes: list[dict], processed_dir: Path = PROCESSED_DIR) -> None:
    """
    Chunk notes text and write chunks.json + sources.json.

    Args:
        notes:         output from ingest.ingest_notes()
        processed_dir: where to write the output files
    """
    # TODO (groupmate): implement chunking strategy.
    raise NotImplementedError(
        "chunk_and_save is not yet implemented — see step 6 of the project spec."
    )
