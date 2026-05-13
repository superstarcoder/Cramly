"""
main.py
=======
Abstract:
    Flask web server for Cramly's study tools. Serves the static frontend
    and exposes quiz generation and answer evaluation endpoints.

    Two quiz generation modes:
      • Notes mode  — reads processed notes from notes/processed/chunks.json
                      and sources from notes/processed/sources.json.
                      Activated by useNotes=true in the request.
      • Search mode — the original web-search-based generation (fallback when
                      useNotes is false or notes haven't been processed yet).

Endpoints:
      GET  /api/quiz-stream      — Server-Sent Events stream of agent decisions.
      POST /api/generate-quiz    — Blocking fallback; same quiz but no streaming.
      POST /api/evaluate-answer  — Grade a short-answer response with GPT.
      GET  /api/notes-status     — Report whether processed notes are available.

Integration point for groupmate (steps 4–6):
    After running the ingest → chunk pipeline, save output to:
        notes/processed/chunks.json   — [{"text": str, "source": str, ...}, ...]
        notes/processed/sources.json  — [{"title": str, "type": str}, ...]
    The /api/quiz-stream endpoint reads these files when useNotes=true.
"""

import json
import os

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from flask_cors import CORS

from src.generate_quiz import QuizGenerator
from src.generate_study_guide import generate_study_guide
from src.utils import load_chunks, load_sources, chunks_to_text

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
    notes                = data.get("notes", "") or ""

    if not (grade_level and major_or_class_level and topic):
        return jsonify({
            "error": "grade_level, major_or_class_level, and topic are all required."
        }), 400

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
        useNotes     (bool) — "true" to generate from notes/processed/

    Each SSE message is a JSON object; see src/generate_quiz.py for event shapes.
    """
    topic         = request.args.get("topic", "").strip()
    difficulty    = request.args.get("difficulty", "Intermediate")
    num_questions = int(request.args.get("numQuestions", 10))
    use_notes     = request.args.get("useNotes", "false").lower() == "true"

    if not topic:
        return _sse_error("Topic is required.")

    notes_text = None
    sources    = None
    if use_notes:
        chunks = load_chunks()
        if not chunks:
            return _sse_error(
                "No processed notes found. "
                "Run the notes pipeline first, then try again."
            )
        notes_text = chunks_to_text(chunks)
        sources    = load_sources()

    def event_stream():
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
        useNotes     (bool)
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    topic         = data.get("topic", "").strip()
    difficulty    = data.get("difficulty", "Intermediate")
    num_questions = int(data.get("numQuestions", 10))
    use_notes     = bool(data.get("useNotes", False))

    if not topic:
        return jsonify({"error": "A topic is required."}), 400

    notes_text = None
    sources    = None
    if use_notes:
        chunks = load_chunks()
        if not chunks:
            return jsonify({
                "error": "No processed notes found. Run the notes pipeline first."
            }), 400
        notes_text = chunks_to_text(chunks)
        sources    = load_sources()

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


@app.route("/api/notes-status")
def notes_status():
    """
    Report whether processed notes are available for quiz generation.
    Called by the frontend on load to enable/disable the 'Use Notes' toggle.

    Response (JSON):
        {"available": bool, "chunk_count": int, "source_count": int}
    """
    chunks  = load_chunks()
    sources = load_sources()
    return jsonify({
        "available":    len(chunks) > 0,
        "chunk_count":  len(chunks),
        "source_count": len(sources),
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"Cramly running at http://localhost:{port}")
    app.run(debug=True, port=port, threaded=True)
