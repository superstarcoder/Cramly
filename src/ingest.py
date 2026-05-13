"""
ingest.py
=========
Abstract:
    Loads raw note files (PDF, PNG, DOCX, TXT) from notes/raw/ and converts
    them to plain text. Step 4 of the pipeline.

    Output is consumed by chunk.py, which saves structured data to
    notes/processed/ for use by generate_quiz.py and generate_study_guide.py.

Expected output format:
    [{"filename": str, "text": str}, ...]

TODO (groupmate): implement per-format loading and OCR/parsing.
"""

from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "notes" / "raw"


def ingest_notes(raw_dir: Path = RAW_DIR) -> list[dict]:
    """
    Load each file in raw_dir and return extracted text.

    Args:
        raw_dir: directory containing uploaded note files

    Returns:
        list of {"filename": str, "text": str} dicts, one per file

    Supported formats to implement: .txt, .pdf, .png, .jpg, .docx
    """
    # TODO (groupmate): implement file loading and OCR/parsing per file type.
    raise NotImplementedError(
        "ingest_notes is not yet implemented — see steps 4-5 of the project spec."
    )
