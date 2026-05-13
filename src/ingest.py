"""
ingest.py
=========
Loads raw note files from notes/raw/ and extracts plain text.
Writes notes/processed/extracted_text.json for chunk.py to consume.

Supported formats:
  .txt            — built-in
  .pdf            — PyMuPDF (fitz); falls back to OCR for scanned pages
  .docx           — python-docx
  .png/.jpg/.jpeg — pytesseract + Pillow (OCR)

Note: pytesseract wraps the Tesseract binary — install it separately:
    brew install tesseract   # macOS
    apt install tesseract-ocr  # Linux
"""

import io
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from docx import Document
from PIL import Image

RAW_DIR       = Path(__file__).parent.parent / "notes" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "notes" / "processed"

SUPPORTED = {".txt", ".pdf", ".docx", ".png", ".jpg", ".jpeg"}

# PDF pages with fewer than this many chars are assumed scanned → OCR fallback
_OCR_THRESHOLD = 50


def _extract_txt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [{"source_file": path.name, "source_type": "txt", "page": 1, "text": text}]


def _extract_pdf(path: Path) -> list[dict]:
    pages = []
    doc = fitz.open(str(path))
    for i, page in enumerate(doc, start=1):
        text = page.get_text().strip()

        # Scanned page: no selectable text → render and OCR
        if len(text) < _OCR_THRESHOLD:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            try:
                text = pytesseract.image_to_string(img).strip()
                if text:
                    print(f"    [ocr] page {i} (scanned) → {len(text)} chars")
            except Exception as e:
                print(f"    [warn] OCR failed on page {i}: {e}")

        if text:
            pages.append({
                "source_file": path.name,
                "source_type": "pdf",
                "page": i,
                "text": text,
            })

    doc.close()
    return pages


def _extract_docx(path: Path) -> list[dict]:
    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [{"source_file": path.name, "source_type": "docx", "page": 1, "text": text}]


def _extract_image(path: Path) -> list[dict]:
    img = Image.open(path)
    try:
        text = pytesseract.image_to_string(img).strip()
    except Exception as e:
        print(f"  [error] OCR failed on {path.name}: {e}")
        return []

    if not text:
        print(f"  [warn] OCR returned no text for {path.name}")
        return []

    return [{"source_file": path.name, "source_type": "image", "page": 1, "text": text}]


def ingest_notes(
    raw_dir: str | Path = RAW_DIR,
    processed_dir: str | Path = PROCESSED_DIR,
) -> list[dict]:
    """
    Extract text from every supported file in raw_dir.

    Writes notes/processed/extracted_text.json and returns the same list.
    Each entry: {"source_file": str, "source_type": str, "page": int, "text": str}
    """
    raw_dir       = Path(raw_dir)
    processed_dir = Path(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)

    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw notes directory not found: {raw_dir}")

    files = sorted(f for f in raw_dir.iterdir() if f.suffix.lower() in SUPPORTED)
    if not files:
        print(f"No supported files found in {raw_dir}")
        return []

    results = []
    for f in files:
        print(f"Ingesting: {f.name}")
        ext = f.suffix.lower()

        if ext == ".txt":
            pages = _extract_txt(f)
        elif ext == ".pdf":
            pages = _extract_pdf(f)
        elif ext == ".docx":
            pages = _extract_docx(f)
        elif ext in {".png", ".jpg", ".jpeg"}:
            pages = _extract_image(f)
        else:
            pages = []

        print(f"  -> {len(pages)} page(s), {sum(len(p['text']) for p in pages)} chars")
        results.extend(pages)

    out_path = processed_dir / "extracted_text.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(results)} page entries to {out_path}")
    return results


if __name__ == "__main__":
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else RAW_DIR
    ingest_notes(raw_dir=raw)
