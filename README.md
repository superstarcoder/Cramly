# Cramly — AI Study Tools

Cramly is an AI-powered study companion with two tools:

- **Quiz** — interactive quizzes generated either from the web (DuckDuckGo
  search) or from a student's own uploaded notes.
- **Study Guide** — dense, exam-prep cheat sheets generated for any topic,
  tuned to the student's grade level, major / class, and optional notes.
  Markdown output with LaTeX math, code blocks, tables, and semantic
  color highlights.

Built with OpenAI (`gpt-4o-mini` for quiz, `gpt-4o` for study guide),
Flask, and vanilla JS.

---

## Project structure

```
Cramly/
├── main.py                    # Flask server — all HTTP endpoints
├── pyproject.toml             # Python dependencies
├── .env.example               # Copy to .env and add OPENAI_API_KEY
│
├── src/
│   ├── generate_quiz.py       # Quiz AI agent (Notes mode + Search mode)
│   ├── generate_study_guide.py# Study guide generation (OpenAI gpt-4o)
│   ├── utils.py               # Helpers: load_chunks, load_sources, chunks_to_text
│   ├── ingest.py              # [TODO groupmate] raw file → text (steps 4-5)
│   ├── chunk.py               # [TODO groupmate] text → chunks.json (step 6)
│   ├── mcp_research.py        # [TODO] MCP research utilities
│   └── cite.py                # [TODO] citation formatting
│
├── prompts/
│   ├── quiz_prompt.txt        # Notes-mode quiz prompt template
│   ├── search_prompt.txt      # Search-mode quiz prompt template
│   └── study_guide_prompt.txt # Study guide prompt template (stub, unused —
│                              # the live prompt lives in generate_study_guide.py)
│
├── notes/
│   ├── raw/                   # Drop uploaded note files here (PDF, PNG, DOCX)
│   ├── processed/             # Pipeline writes chunks.json + sources.json here
│   └── outputs/               # Generated quiz.json + study_guide.md saved here
│
└── static/
    ├── index.html             # Main menu — choose Quiz or Study Guide
    ├── quiz.html              # 4-screen quiz SPA (input → agent → quiz → results)
    ├── quiz.js                # Quiz frontend logic and SSE client
    ├── study_guide.html       # 3-screen study guide SPA (input → loading → display)
    │                          # Inline JS handles form, fetch, marked + KaTeX render
    └── style.css              # Shared paper/cream theme with auto dark mode
```

---

## Architecture

### Quiz

Two generation modes, selected at request time:

**Notes mode** (`useNotes=true`)
> User's processed notes are read from `notes/processed/chunks.json` and
> passed directly to GPT as context. No web search. Fast (single API call).
> Requires the notes pipeline (steps 4-6) to have run first.

**Search mode** (`useNotes=false`, default)
> GPT runs a tool-use loop, calling DuckDuckGo to find textbook summaries,
> Quizlet cards, interview questions, and practice problems. Slower (4-6
> searches), but works without any notes.

### Study Guide

A single blocking call to `gpt-4o`. Inputs:

- `grade_level` — High School / College Freshman / Sophomore / Junior / Senior / Graduate
- `major_or_class_level` — e.g. "CS — Data Structures"
- `topic` — what the cheat sheet is about
- `notes` *(optional)* — freeform notes pasted into the form, or uploaded as a `.txt` / `.md` file. Wrapped in `<student_notes>...</student_notes>` and woven into the prompt so the LLM prefers the student's framing where it matches canonical material.

Output is pure Markdown saved to `notes/outputs/study_guide.md`. The
viewer (`/study_guide.html`) renders it with [marked](https://marked.js.org)
+ [KaTeX](https://katex.org/), and recognizes a few inline semantic HTML
spans (`<span class="key|warn|tip|heading|subheading|label">…</span>`) for
color-coded highlights.

---

## Code flow

### Main menu → tool selection

```
Browser  GET /
  ▼
main.py → static/index.html        (tile picker: Quiz | Study Guide)
            │
            ├── /quiz.html         → quiz SPA
            └── /study_guide.html  → study guide SPA
```

### Quiz — Notes mode

```
Browser (useNotes=true)
  │  GET /api/quiz-stream?topic=...&useNotes=true
  ▼
main.py
  ├── load_chunks()       reads notes/processed/chunks.json
  ├── chunks_to_text()    joins + truncates to 50,000 chars
  └── generate_quiz_stream(notes_text=...)
        │
        src/generate_quiz.py  _stream_from_notes()
          ├── yield {"type": "notes_loaded", ...}   → browser: "Analyzing notes…"
          ├── GPT call with notes embedded in prompt (no tools)
          ├── yield {"type": "generating", ...}     → browser: "Composing quiz…"
          └── yield {"type": "complete", "quiz": {}}→ browser: renders quiz
```

### Quiz — Search mode

```
Browser (useNotes=false)
  │  GET /api/quiz-stream?topic=...
  ▼
main.py → generate_quiz_stream(notes_text=None)
        │
        src/generate_quiz.py  _stream_from_search()
          │  gpt-4o-mini tool-use loop (up to 10 iterations)
          ├── yield {"type": "search_start", "query": "..."}  → browser log
          │   DuckDuckGo executes search
          ├── yield {"type": "search_done", "count": 5, ...}  → browser log
          │   (repeated for each search)
          ├── yield {"type": "generating", ...}               → browser log
          └── yield {"type": "complete", "quiz": {}}          → quiz starts
```

### Short-answer grading

```
Browser  POST /api/evaluate-answer  {question, model_answer, key_points, student_answer}
  ▼
main.py → QuizGenerator.evaluate_short_answer()
  └── GPT returns {"score": "correct|partial|incorrect", "feedback": "..."}
```

### Study Guide

```
Browser (study_guide.html)
  │  Form: topic, grade_level, major_or_class_level, notes (typed or uploaded)
  │  POST /api/generate-study-guide  {grade_level, major_or_class_level, topic, notes}
  ▼
main.py → src/generate_study_guide.py  generate_study_guide(...)
            ├── builds user_prompt; appends <student_notes>…</student_notes> if notes given
            ├── OpenAI gpt-4o single call with the system prompt + user_prompt
            ├── writes Markdown to notes/outputs/study_guide.md
            └── returns markdown string
  │
  ▼
Browser
  ├── receives {ok: true, markdown: "..."}
  ├── marked.parse(markdown)        Markdown → HTML (math spans protected)
  ├── KaTeX renderMathInElement()   $…$ and $$…$$ → rendered math
  └── swaps to display screen, shows rendered guide
```

The Markdown file is also served separately at `GET /study-guide.md`
so it can be linked, downloaded, or re-rendered without regenerating.

### Notes pipeline integration (groupmate — steps 4-6)

```
src/ingest.py     load files from notes/raw/  →  [{"filename", "text"}, ...]
src/chunk.py      split + save               →  notes/processed/chunks.json
                                                 notes/processed/sources.json
main.py           /api/notes-status           →  {"available": bool, "chunk_count": int}
main.py           /api/quiz-stream?useNotes=true  reads the files above
```

**chunks.json format:**
```json
[{"text": "...", "source": "lecture1.pdf", "chunk_id": 0}, ...]
```
**sources.json format:**
```json
[{"title": "lecture1.pdf", "type": "notes"}, ...]
```

---

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # Mac / Linux
# or: venv\Scripts\activate   # Windows
```

### 2. Install dependencies

```bash
pip install -e .
```

This pulls in everything from `pyproject.toml` — Flask, flask-cors,
python-dotenv, openai, duckduckgo-search, etc. No extra packages are
needed for the study guide; it reuses the existing `openai` client.

### 3. Configure environment variables

```bash
cp .env.example .env
# Open .env and set:
#   OPENAI_API_KEY=sk-...
```

### 4. Run the server

```bash
python main.py
```

Open <http://localhost:8080> in your browser. You'll land on the main
menu where you can pick **Quiz** or **Study Guide**.

> **macOS note:** the default port is **8080**, not 5000. Port 5000 on
> macOS Monterey+ is silently hijacked by AirPlay Receiver, which returns
> `403 Forbidden`. If you want a different port:
> ```bash
> PORT=9000 python main.py
> ```

### 5. (Optional) Generate a study guide from the CLI

The Study Guide can also be generated without the UI:

```bash
python3 src/generate_study_guide.py
```

The file is written to `notes/outputs/study_guide.md`. Edit the
`if __name__ == "__main__"` block at the bottom of the script to change
the topic / grade level / major.

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/` | Main menu (tile picker) |
| `GET`  | `/quiz.html` | Quiz SPA |
| `GET`  | `/study_guide.html` | Study Guide SPA |
| `GET`  | `/study-guide.md` | Raw Markdown of the most recently generated study guide |
| `GET`  | `/api/quiz-stream` | SSE stream of quiz agent events |
| `POST` | `/api/generate-quiz` | Blocking quiz generation |
| `POST` | `/api/evaluate-answer` | Grade a short-answer response |
| `POST` | `/api/generate-study-guide` | Generate a study guide cheat sheet |
| `GET`  | `/api/notes-status` | Check if processed notes exist |

### `GET /api/quiz-stream` query params

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `topic` | string | required | Subject to quiz on |
| `difficulty` | string | `Intermediate` | `Beginner` / `Intermediate` / `Advanced` |
| `numQuestions` | int | `10` | `5`, `10`, or `15` |
| `useNotes` | bool | `false` | Generate from `notes/processed/` instead of web |

### `POST /api/generate-study-guide` body (JSON)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | yes | What the cheat sheet is about |
| `grade_level` | string | yes | e.g. `College Sophomore` |
| `major_or_class_level` | string | yes | e.g. `CS — Data Structures` |
| `notes` | string | no | Freeform notes to weave into the guide |

Response: `{"ok": true, "markdown": "<full markdown>"}`. The same
markdown is saved to `notes/outputs/study_guide.md`.

### SSE event types (quiz)

| `type` | Fields | When |
|--------|--------|------|
| `notes_loaded` | `message`, `char_count` | Notes mode: notes read into context |
| `search_start` | `query` | Search mode: agent begins a search |
| `search_done` | `query`, `count`, `titles` | Search mode: results received |
| `generating` | `message` | GPT is writing the quiz JSON |
| `complete` | `quiz` | Quiz object is ready |
| `error` | `message` | Something went wrong |

---

## Frontend notes

- **Shared theme** — `static/style.css` is the single source of truth for
  the UI palette, typography (Inter + Fraunces + JetBrains Mono), and
  component styles. Light by default, dark via `prefers-color-scheme`.
- **Study guide markdown viewer** styles are scoped to `.markdown-view`
  inside `study_guide.html` so they don't clash with the form/loading
  screens or the quiz UI.
- **LaTeX math** in study guides uses `$…$` (inline) and `$$…$$` (display).
  The viewer registers a `marked` extension that protects math spans from
  Markdown parsing so underscores, asterisks, and backslashes inside math
  reach KaTeX intact.
- **Semantic color spans** in study guide markdown:
  `key`, `warn`, `tip`, `heading`, `subheading`, `label`. Defined in
  `study_guide.html`'s scoped CSS with dark-mode variants.
- **Notes file upload** on the study guide form accepts `.txt`, `.md`,
  `.markdown`. The file is read entirely in the browser (`FileReader`)
  and dropped into the notes textarea — no upload endpoint needed.
  PDF/DOCX support would need a backend parser (`pypdf`, `python-docx`)
  wired into the `src/ingest.py` step.
