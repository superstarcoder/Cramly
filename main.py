"""
main.py
=======
Abstract:
    Flask web server for Cramly's study tools. Serves the static frontend
    and exposes quiz generation and answer evaluation endpoints.

    Two quiz generation modes, chosen automatically per request:
      • Notes mode  — used whenever notes/processed/chunks.json has content.
      • Search mode — fallback when no processed notes are available; runs the
                      original web-search-based generation.

Endpoints:
      GET  /api/quiz-stream      — Server-Sent Events stream of agent decisions.
      POST /api/generate-quiz    — Blocking fallback; same quiz but no streaming.
      POST /api/evaluate-answer  — Grade a short-answer response with GPT.
      GET  /api/notes-status     — Report whether processed notes are available.
      POST /api/upload-notes     — Save uploaded raw note files.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from flask_cors import CORS
from werkzeug.utils import secure_filename

from src.chunk import chunk_notes
from src.generate_quiz import QuizGenerator
from src.generate_study_guide import generate_study_guide
from src.handwritten_ingest import process_handwritten_notes
from src.ingest import ingest_notes
from src.mcp_research import research_with_mcp
from src.utils import load_all_note_chunks, chunks_to_sources, chunks_to_text

load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

generator = QuizGenerator()


def _sse_error(msg: str) -> Response:
    """Return a single SSE error event as a Response."""
    def gen():
        yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"
    return Response(gen(), mimetype="text/event-stream")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main menu (Quiz vs. Study Guide)."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/study-guide.md")
def study_guide_markdown():
    """Serve the generated study guide markdown to the viewer."""
    return send_from_directory("notes/outputs", "study_guide.md", mimetype="text/markdown")


@app.route("/api/generate-study-guide", methods=["POST"])
def generate_study_guide_endpoint():
    """
    Generate a study guide cheat sheet and save it to notes/outputs/study_guide.md.

    Request body (JSON):
        grade_level          (str)
        major_or_class_level (str)
        topic                (str)

    Response (JSON): {"ok": True, "markdown": "<full markdown>"}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    grade_level          = data.get("grade_level", "").strip()
    major_or_class_level = data.get("major_or_class_level", "").strip()
    topic                = data.get("topic", "").strip()
    notes                = (data.get("notes", "") or "").strip()

    if not (grade_level and major_or_class_level and topic):
        return jsonify({
            "error": "grade_level, major_or_class_level, and topic are all required."
        }), 400

    # Run MCP web research to enrich context (skips silently if TAVILY_API_KEY unset).
    if os.getenv("TAVILY_API_KEY"):
        research_with_mcp(topic, grade_level=grade_level, major=major_or_class_level)

    # If the user didn't paste notes, fall back to processed + external chunks.
    if not notes:
        chunks = load_all_note_chunks()
        if chunks:
            notes = chunks_to_text(chunks)

    try:
        markdown = generate_study_guide(grade_level, major_or_class_level, topic, notes)
        return jsonify({"ok": True, "markdown": markdown})
    except Exception as exc:
        print(f"[ERROR] generate-study-guide: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/quiz-stream")
def quiz_stream():
    """
    Server-Sent Events endpoint — streams every agent decision to the browser.

    Query params:
        topic        (str)  — subject to quiz on
        difficulty   (str)  — "Beginner" | "Intermediate" | "Advanced"
        numQuestions (int)  — 5, 10, or 15

    Notes mode is selected automatically when processed notes are available;
    otherwise the agent falls back to web search.

    Each SSE message is a JSON object; see src/generate_quiz.py for event shapes.
    """
    topic         = request.args.get("topic", "").strip()
    difficulty    = request.args.get("difficulty", "Intermediate")
    num_questions = int(request.args.get("numQuestions", 10))

    if not topic:
        return _sse_error("Topic is required.")

    def event_stream():
        # Run MCP web research before building the quiz context.
        if os.getenv("TAVILY_API_KEY"):
            msg_start = f'Enriching with web research on "{topic}"...'
            yield f"data: {json.dumps({'type': 'mcp_research', 'message': msg_start})}\n\n"
            research_with_mcp(topic)
            yield f"data: {json.dumps({'type': 'mcp_research', 'message': 'Web research complete — sources added.'})}\n\n"

        chunks = load_all_note_chunks()
        notes_text = chunks_to_text(chunks) if chunks else None
        sources    = chunks_to_sources(chunks) if chunks else None

        for event in generator.generate_quiz_stream(
            topic, difficulty, num_questions, notes_text, sources
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


@app.route("/api/generate-quiz", methods=["POST"])
def generate_quiz():
    """
    Blocking fallback — same quiz but waits for the full result.

    Request body (JSON):
        topic        (str)
        difficulty   (str)
        numQuestions (int)

    Uses processed notes if any exist; otherwise falls back to web search.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    topic         = data.get("topic", "").strip()
    difficulty    = data.get("difficulty", "Intermediate")
    num_questions = int(data.get("numQuestions", 10))

    if not topic:
        return jsonify({"error": "A topic is required."}), 400

    if os.getenv("TAVILY_API_KEY"):
        research_with_mcp(topic)

    chunks = load_all_note_chunks()
    notes_text = chunks_to_text(chunks) if chunks else None
    sources    = chunks_to_sources(chunks) if chunks else None

    try:
        quiz = generator.generate_quiz(topic, difficulty, num_questions, notes_text, sources)
        return jsonify(quiz)
    except Exception as exc:
        print(f"[ERROR] generate-quiz: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/evaluate-answer", methods=["POST"])
def evaluate_answer():
    """
    Grade a student's short-answer response using GPT.

    Request body (JSON):
        question       (str)
        model_answer   (str)
        key_points     (list[str])
        student_answer (str)

    Response (JSON): {"score": "correct|partial|incorrect", "feedback": "..."}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    try:
        result = generator.evaluate_short_answer(
            question       = data.get("question", ""),
            model_answer   = data.get("model_answer", ""),
            key_points     = data.get("key_points", []),
            student_answer = data.get("student_answer", ""),
        )
        return jsonify(result)
    except Exception as exc:
        print(f"[ERROR] evaluate-answer: {exc}")
        return jsonify({"error": str(exc)}), 500


PROJECT_ROOT = Path(__file__).parent
UPLOAD_DIRS = {
    "digital":     PROJECT_ROOT / "notes" / "raw",
    "handwritten": PROJECT_ROOT / "notes" / "handwritten" / "raw",
}
ALLOWED_EXTS = {
    "digital":     {".txt", ".pdf", ".docx", ".md"},
    "handwritten": {".pdf", ".png", ".jpg", ".jpeg"},
}


@app.route("/api/upload-notes", methods=["POST"])
def upload_notes():
    """
    Save uploaded note files to the appropriate raw directory.

    Form fields:
        kind   — "digital" | "handwritten"
        files  — one or more files (input name "files")

    Digital notes go to notes/raw/.
    Handwritten notes go to notes/handwritten/raw/.
    """
    kind = (request.form.get("kind") or "").strip().lower()
    if kind not in UPLOAD_DIRS:
        return jsonify({"error": "kind must be 'digital' or 'handwritten'."}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided."}), 400

    target_dir = UPLOAD_DIRS[kind]
    target_dir.mkdir(parents=True, exist_ok=True)
    allowed = ALLOWED_EXTS[kind]

    saved, skipped = [], []
    for f in files:
        if not f or not f.filename:
            continue
        name = secure_filename(f.filename)
        ext  = Path(name).suffix.lower()
        if ext not in allowed:
            skipped.append({"name": f.filename, "reason": f"unsupported extension {ext or '(none)'}"})
            continue

        dest = target_dir / name
        if dest.exists():
            stem = dest.stem
            i = 1
            while dest.exists():
                dest = target_dir / f"{stem}-{i}{ext}"
                i += 1
        f.save(str(dest))
        saved.append(dest.name)

    processed = None
    process_error = None
    if saved:
        try:
            if kind == "digital":
                pages = ingest_notes()
                chunk_notes()
                processed = {"pages": len(pages)}
            else:
                processed = process_handwritten_notes()
        except Exception as exc:
            print(f"[ERROR] post-upload processing ({kind}): {exc}")
            process_error = str(exc)

    return jsonify({
        "ok":            True,
        "saved":         saved,
        "skipped":       skipped,
        "processed":     processed,
        "process_error": process_error,
    })


@app.route("/api/notes-status")
def notes_status():
    """
    Report whether processed notes are available for quiz generation.
    Called by the frontend on load to enable/disable the 'Use Notes' toggle.

    Response (JSON):
        {"available": bool, "chunk_count": int, "source_count": int}
    """
    chunks = load_all_note_chunks()
    return jsonify({
        "available":    len(chunks) > 0,
        "chunk_count":  len(chunks),
        "source_count": len(set(
            (c.get("citation", {}).get("source_file") or c.get("source_file") or c.get("source", ""))
            for c in chunks
        )),
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"Cramly running at http://localhost:{port}")
    app.run(debug=True, port=port, threaded=True)
