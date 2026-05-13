"""
handwritten_ingest.py
=====================
Processes handwritten and math-heavy notes using a vision LLM instead of
standard OCR. Regular OCR struggles with handwritten equations, graphs, and
shaded regions — this pipeline sends each page as an image to gpt-4o.

Input:   notes/handwritten/raw/          (.pdf, .png, .jpg, .jpeg)
Output:  notes/handwritten/processed/
           handwritten_pages.json        structured per-page extractions
           handwritten_chunks.json       flat text chunks for the quiz pipeline
           page_images/                  rendered PNG for each page processed

Run:
    python -m src.handwritten_ingest
"""

import base64
import json
import os
import sys
from pathlib import Path

import fitz  # PyMuPDF
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

load_dotenv()

PROJECT_ROOT  = Path(__file__).parent.parent
RAW_DIR       = PROJECT_ROOT / "notes" / "handwritten" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "notes" / "handwritten" / "processed"

SUPPORTED    = {".pdf", ".png", ".jpg", ".jpeg"}
VISION_MODEL = "gpt-4o"

VISION_PROMPT = """\
You are analyzing a page of handwritten math or science notes.
Extract ALL content visible on the page and return ONLY valid JSON — no markdown, no prose.

Required JSON schema (omit nothing, use empty list/string if not present):
{
  "topics":       ["list of topic names visible on this page"],
  "formulas":     ["each formula or equation as a readable string, e.g. f(x,y) = (3x+2y)/240"],
  "graphs": [
    {
      "description":    "what the graph shows",
      "boundaries":     ["inequality or equation for each boundary, e.g. x + 2y <= 10"],
      "shaded_region":  "description of the shaded area, or empty string"
    }
  ],
  "worked_steps": ["step 1 description", "step 2 description", "..."],
  "summary":      "one-sentence summary of what this page is about",
  "confidence":   "high | medium | low  (how legible/complete the page was)"
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode_bytes(img_bytes: bytes) -> str:
    return base64.b64encode(img_bytes).decode("utf-8")


def _call_vision(client: OpenAI, img_bytes: bytes) -> dict:
    """Send an image to gpt-4o and return the parsed extraction dict."""
    response = client.chat.completions.create(
        model=VISION_MODEL,
        response_format={"type": "json_object"},
        max_tokens=2000,
        messages=[
            {"role": "system", "content": VISION_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{_encode_bytes(img_bytes)}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all content from this handwritten notes page.",
                    },
                ],
            },
        ],
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _normalize(raw: dict) -> dict:
    """Guarantee all expected keys exist with the right types."""
    return {
        "topics":       raw.get("topics") or [],
        "formulas":     raw.get("formulas") or [],
        "graphs":       raw.get("graphs") or [],
        "worked_steps": raw.get("worked_steps") or [],
        "summary":      raw.get("summary") or "",
        "confidence":   raw.get("confidence") or "low",
    }


def _page_to_text(page: dict) -> str:
    """Build a readable text chunk from a structured page extraction."""
    parts = []
    if page.get("summary"):
        parts.append(page["summary"])
    if page.get("topics"):
        parts.append("Topics: " + ", ".join(page["topics"]) + ".")
    if page.get("formulas"):
        parts.append("Formulas: " + " | ".join(page["formulas"]) + ".")
    for g in page.get("graphs", []):
        g_parts = []
        if g.get("description"):
            g_parts.append(g["description"])
        if g.get("boundaries"):
            g_parts.append("Boundaries: " + ", ".join(g["boundaries"]) + ".")
        if g.get("shaded_region"):
            g_parts.append("Shaded region: " + g["shaded_region"])
        parts.append(" ".join(g_parts))
    if page.get("worked_steps"):
        parts.append("Steps: " + " → ".join(page["worked_steps"]) + ".")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def process_handwritten_notes(
    raw_dir: str | Path = RAW_DIR,
    processed_dir: str | Path = PROCESSED_DIR,
) -> dict:
    """
    Process handwritten note files through the vision pipeline.

    Returns a summary dict: {"files": int, "pages": int, "chunks": int}
    """
    raw_dir       = Path(raw_dir)
    processed_dir = Path(processed_dir)
    image_dir     = processed_dir / "page_images"

    processed_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    if not raw_dir.exists() or not any(True for _ in raw_dir.iterdir()):
        print(f"No files found in {raw_dir} — add handwritten notes and rerun.")
        return {"files": 0, "pages": 0, "chunks": 0}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set — add it to your .env file.")
        return {"files": 0, "pages": 0, "chunks": 0}

    client = OpenAI(api_key=api_key)

    # Verify the key works before burning through all pages
    try:
        client.models.list()
    except Exception as e:
        print(f"OpenAI API error ({type(e).__name__}): {e}")
        return {"files": 0, "pages": 0, "chunks": 0}

    files  = sorted(f for f in raw_dir.iterdir() if f.suffix.lower() in SUPPORTED)

    if not files:
        print(f"No supported files (.pdf/.png/.jpg/.jpeg) found in {raw_dir}")
        return {"files": 0, "pages": 0, "chunks": 0}

    pages  = []
    chunks = []
    chunk_counter = 0

    for file in files:
        print(f"\nProcessing: {file.name}")
        ext = file.suffix.lower()

        if ext == ".pdf":
            doc = fitz.open(str(file))
            for page_num, pdf_page in enumerate(doc, start=1):
                page_id   = f"{file.stem}_pdf_page_{page_num:03d}"
                img_name  = f"{file.stem}_page_{page_num:03d}.png"
                img_path  = image_dir / img_name
                rel_path  = str(img_path.relative_to(PROJECT_ROOT))

                pix       = pdf_page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                img_path.write_bytes(img_bytes)

                print(f"  page {page_num}/{len(doc)} → vision extraction...", end=" ", flush=True)
                try:
                    extracted = _normalize(_call_vision(client, img_bytes))
                    print(f"done ({extracted['confidence']} confidence)")
                except Exception as e:
                    print(f"failed ({type(e).__name__}): {e}")
                    continue

                page_entry = {
                    "page_id":      page_id,
                    "source_file":  file.name,
                    "page":         page_num,
                    "image_path":   rel_path,
                    **extracted,
                }
                pages.append(page_entry)

                chunk_id = f"hw_chunk_{chunk_counter:03d}"
                chunks.append({
                    "chunk_id":      chunk_id,
                    "page_id":       page_id,
                    "source_file":   file.name,
                    "page":          page_num,
                    "text":          _page_to_text(page_entry),
                    "evidence_type": "handwritten_visual_math",
                    "citation": {
                        "source_file": file.name,
                        "page":        page_num,
                        "page_id":     page_id,
                    },
                })
                chunk_counter += 1

            doc.close()

        else:
            # standalone image
            page_id  = f"{file.stem}_img_001"
            img_name = f"{file.stem}_img_001.png"
            img_path = image_dir / img_name
            rel_path = str(img_path.relative_to(PROJECT_ROOT))

            img = Image.open(file)
            img.save(img_path, "PNG")
            img_bytes = img_path.read_bytes()

            print(f"  → vision extraction...", end=" ", flush=True)
            try:
                extracted = _normalize(_call_vision(client, img_bytes))
                print(f"done ({extracted['confidence']} confidence)")
            except Exception as e:
                print(f"failed: {e}")
                continue

            page_entry = {
                "page_id":     page_id,
                "source_file": file.name,
                "page":        1,
                "image_path":  rel_path,
                **extracted,
            }
            pages.append(page_entry)

            chunk_id = f"hw_chunk_{chunk_counter:03d}"
            chunks.append({
                "chunk_id":      chunk_id,
                "page_id":       page_id,
                "source_file":   file.name,
                "page":          1,
                "text":          _page_to_text(page_entry),
                "evidence_type": "handwritten_visual_math",
                "citation": {
                    "source_file": file.name,
                    "page":        1,
                    "page_id":     page_id,
                },
            })
            chunk_counter += 1

    (processed_dir / "handwritten_pages.json").write_text(
        json.dumps(pages, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (processed_dir / "handwritten_chunks.json").write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if not chunks:
        print("\nWarning: no chunks were produced — check that your files are legible.")

    return {"files": len(files), "pages": len(pages), "chunks": len(chunks)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = process_handwritten_notes()
    print(
        f"\nDone — {result['files']} file(s), "
        f"{result['pages']} page(s), "
        f"{result['chunks']} chunk(s)"
    )
    print(f"  pages:  {PROCESSED_DIR / 'handwritten_pages.json'}")
    print(f"  chunks: {PROCESSED_DIR / 'handwritten_chunks.json'}")
    print(f"  images: {PROCESSED_DIR / 'page_images/'}")
