# Cramly: AI Study Tools

Cramly is an AI-powered study companion with two tools:

- **Quiz**: interactive quizzes generated either from a student's own uploaded
  notes (when available) or from the web via DuckDuckGo search.
- **Study Guide**: dense, exam-prep cheat sheets generated for any topic,
  tuned to the student's grade level, major / class, and optional notes.
  Markdown output with LaTeX math, code blocks, tables, and semantic
  color highlights.

Both tools share the **same notes pipeline**: upload digital files (PDF,
DOCX, TXT, MD) and/or handwritten files (PDF, PNG, JPG) directly from the
UI, and the backend ingests, OCRs, and chunks them automatically. Whenever
processed notes exist, the tools use them; otherwise they fall back to web
search (quiz) or topic-only generation (study guide).

Built with OpenAI (`gpt-4o-mini` for quiz, `gpt-4o` for study guide and the
handwritten-vision pipeline), Flask, and vanilla JS.

---

## Setup

### 1. Install Tesseract (system dependency for OCR)

`pytesseract` is a thin wrapper over the Tesseract binary, which Python
can't install. Get it from your package manager:

```bash
brew install tesseract          # macOS
sudo apt install tesseract-ocr  # Debian / Ubuntu
```

Without Tesseract, scanned PDFs and image uploads in the digital pipeline
fall back to empty text. (The handwritten pipeline uses OpenAI vision and
does not need Tesseract.)

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # Mac / Linux
# or: venv\Scripts\activate   # Windows
```

### 3. Install Python dependencies

```bash
pip install -e .
```
or 
```bash
pip install -r requirements.txt
```

This pulls in everything from `pyproject.toml`: Flask, flask-cors,
python-dotenv, openai, duckduckgo-search, PyMuPDF, python-docx,
pytesseract, Pillow, tavily-python.

### 4. Configure environment variables

```bash
cp .env.example .env
# Open .env and set:
#   OPENAI_API_KEY=sk-...
```

### 5. Run the server

```bash
python main.py
```

Open <http://localhost:8080> in your browser. You'll land on the main
menu where you can pick **Quiz** or **Study Guide**. Either page lets you
upload notes directly, no CLI step required.

> **macOS note:** the default port is **8080**, not 5000. Port 5000 on
> macOS Monterey+ is silently hijacked by AirPlay Receiver, which returns
> `403 Forbidden`. If you want a different port:
> ```bash
> PORT=9000 python main.py
> ```

### 6. (Optional) Run the notes pipeline from the CLI

The upload UI runs everything automatically, but you can also drive the
pipelines manually:

```bash
# Digital notes (after dropping files into notes/raw/):
python -m src.ingest
python -m src.chunk

# Handwritten notes (after dropping files into notes/handwritten/raw/):
python -m src.handwritten_ingest
```

### 7. (Optional) Generate a study guide from the CLI

```bash
python3 src/generate_study_guide.py
```

The file is written to `notes/outputs/study_guide.md`. Edit the
`if __name__ == "__main__"` block at the bottom of the script to change
the topic / grade level / major.

---

## Project structure

```
Cramly/
├── main.py                    # Flask server: all HTTP endpoints
├── pyproject.toml             # Python dependencies
├── .env.example               # Copy to .env and add OPENAI_API_KEY
│
├── src/
│   ├── generate_quiz.py       # Quiz AI agent (Notes mode + Search mode)
│   ├── generate_study_guide.py# Study guide generation (OpenAI gpt-4o)
│   ├── utils.py               # load_all_note_chunks, chunks_to_text, chunks_to_sources
│   ├── ingest.py              # notes/raw -> notes/processed/extracted_text.json
│   ├── chunk.py               # extracted_text.json -> chunks.json + sources.json
│   ├── handwritten_ingest.py  # notes/handwritten/raw -> handwritten_chunks.json (vision API)
│   ├── mcp_research.py        # MCP research utilities
│   └── cite.py                # citation formatting
│
├── prompts/
│   ├── quiz_prompt.txt        # Notes-mode quiz prompt template
│   ├── search_prompt.txt      # Search-mode quiz prompt template
│   └── study_guide_prompt.txt # Study guide prompt template (stub, unused;
│                              # the live prompt lives in generate_study_guide.py)
│
├── notes/
│   ├── raw/                   # Digital uploads land here (PDF / DOCX / TXT / MD / images)
│   ├── processed/             # ingest+chunk write extracted_text.json,
│   │                          # chunks.json, sources.json
│   ├── handwritten/
│   │   ├── raw/               # Handwritten uploads land here (PDF / PNG / JPG / JPEG)
│   │   └── processed/         # Vision pipeline writes handwritten_chunks.json
│   └── outputs/               # Generated quiz.json + study_guide.md saved here
│
└── static/
    ├── index.html             # Main menu: choose Quiz or Study Guide
    ├── quiz.html              # 4-screen quiz SPA (input -> agent -> quiz -> results)
    ├── quiz.js                # Quiz frontend logic, SSE client, upload handlers
    ├── study_guide.html       # 3-screen study guide SPA (input -> loading -> display)
    │                          # Inline JS handles uploads, form, fetch, marked + KaTeX
    └── style.css              # Shared paper/cream theme with auto dark mode
```

---

## Architecture

### Notes pipeline (shared by both tools)

Upload happens **from the UI on either tool's input screen**: both the
quiz and study-guide pages expose the same two upload groups:

1. **Digital notes** (`.txt`, `.md`, `.pdf`, `.docx`)
2. **Handwritten notes** (`.pdf`, `.png`, `.jpg`, `.jpeg`)

Each upload hits `POST /api/upload-notes`, which saves the file to the
right `raw/` directory and **immediately runs the corresponding processing
pipeline synchronously** before responding:

| `kind`        | Save to                       | Pipeline run on save                                        | Output                                          |
|---------------|-------------------------------|-------------------------------------------------------------|-------------------------------------------------|
| `digital`     | `notes/raw/`                  | `ingest_notes()` then `chunk_notes()`                       | `notes/processed/{chunks,sources}.json`         |
| `handwritten` | `notes/handwritten/raw/`      | `process_handwritten_notes()` (OpenAI vision per page)      | `notes/handwritten/processed/handwritten_chunks.json` |

> Note: each upload re-runs the pipeline against the **entire** `raw/`
> directory, not just the new file. Deleting a file from `raw/` and
> re-uploading something else drops the deleted file's chunks. This is
> usually what you want.

`load_all_note_chunks()` in `src/utils.py` returns the combined chunk list
from both pipelines, and both downstream tools call it to discover
whatever notes are currently available.

### Quiz

Mode is selected automatically per request:

**Notes mode** (used whenever `load_all_note_chunks()` returns chunks)
> Notes are read, joined into a single string, truncated to 50,000 chars,
> and passed directly to GPT as context. No web search. Fast (single API
> call).

**Search mode** (fallback when no processed notes exist)
> GPT runs a tool-use loop, calling DuckDuckGo to find textbook summaries,
> Quizlet cards, interview questions, and practice problems. Slower (4-6
> searches), but works without any notes.

### Study Guide

A single blocking call to `gpt-4o`. Inputs:

- `grade_level`: High School / College Freshman / Sophomore / Junior / Senior / Graduate
- `major_or_class_level`: e.g. "CS, Data Structures"
- `topic`: what the cheat sheet is about
- `notes` *(optional)*: freeform notes pasted into the textarea. If the
  textarea is empty, the backend auto-loads whatever's in the processed
  notes pipeline (digital + handwritten chunks concatenated) and uses
  that. Notes are wrapped in `<student_notes>...</student_notes>` and
  woven into the prompt so the LLM prefers the student's framing where
  it matches canonical material.

Output is pure Markdown saved to `notes/outputs/study_guide.md`. The
viewer (`/study_guide.html`) renders it with [marked](https://marked.js.org)
+ [KaTeX](https://katex.org/), and recognizes a few inline semantic HTML
spans (`<span class="key|warn|tip|heading|subheading|label">…</span>`) for
color-coded highlights.

---

## Code flow

### Main menu -> tool selection

```
Browser  GET /
  v
main.py -> static/index.html        (tile picker: Quiz | Study Guide)
            |
            +-- /quiz.html         -> quiz SPA
            +-- /study_guide.html  -> study guide SPA
```

### Notes upload (shared by both tools)

```
Browser (quiz.html or study_guide.html)
  |  Upload digital notes button   -> POST /api/upload-notes (kind=digital, files=[...])
  |  Upload handwritten button     -> POST /api/upload-notes (kind=handwritten, files=[...])
  v
main.py  upload_notes()
  +-- secure_filename(); save each file to notes/raw or notes/handwritten/raw
  +-- kind=digital      -> ingest_notes() + chunk_notes()
  |                       writes notes/processed/{extracted_text,chunks,sources}.json
  +-- kind=handwritten  -> process_handwritten_notes()
                          writes notes/handwritten/processed/handwritten_chunks.json
  |
  v
Browser
  +-- status line shows "Saved N file(s), processed M page(s)"
  +-- refreshes /api/notes-status badge so the chunk count updates immediately
```

### Quiz, Notes mode (auto)

```
Browser
  |  GET /api/quiz-stream?topic=...&difficulty=...&numQuestions=...
  v
main.py
  +-- load_all_note_chunks()   reads notes/processed + notes/handwritten/processed
  |   if chunks exist -> fall into Notes mode
  +-- chunks_to_text()         joins + truncates to 50,000 chars
  +-- chunks_to_sources()      dedupes source filenames for citation
  +-- generate_quiz_stream(notes_text=..., sources=...)
        |
        src/generate_quiz.py  _stream_from_notes()
          +-- yield {"type": "notes_loaded", ...}   -> browser: "Analyzing notes..."
          +-- GPT call with notes embedded in prompt (no tools)
          +-- yield {"type": "generating", ...}     -> browser: "Composing quiz..."
          +-- yield {"type": "complete", "quiz": {}} -> browser: renders quiz
```

### Quiz, Search mode (fallback when no notes)

```
Browser
  |  GET /api/quiz-stream?topic=...
  v
main.py -> no chunks found -> generate_quiz_stream(notes_text=None)
        |
        src/generate_quiz.py  _stream_from_search()
          |  gpt-4o-mini tool-use loop (up to 10 iterations)
          +-- yield {"type": "search_start", "query": "..."}  -> browser log
          |   DuckDuckGo executes search
          +-- yield {"type": "search_done", "count": 5, ...}  -> browser log
          |   (repeated for each search)
          +-- yield {"type": "generating", ...}               -> browser log
          +-- yield {"type": "complete", "quiz": {}}          -> quiz starts
```

### Short-answer grading

```
Browser  POST /api/evaluate-answer  {question, model_answer, key_points, student_answer}
  v
main.py -> QuizGenerator.evaluate_short_answer()
  +-- GPT returns {"score": "correct|partial|incorrect", "feedback": "..."}
```

### Study Guide

```
Browser (study_guide.html)
  |  Form: topic, grade_level, major_or_class_level, notes (optional inline paste)
  |  POST /api/generate-study-guide  {grade_level, major_or_class_level, topic, notes}
  v
main.py
  +-- if notes is empty -> load_all_note_chunks() + chunks_to_text() (auto-fallback)
  +-- src/generate_study_guide.py  generate_study_guide(...)
            +-- builds user_prompt; appends <student_notes>...</student_notes> if notes given
            +-- OpenAI gpt-4o single call with the system prompt + user_prompt
            +-- writes Markdown to notes/outputs/study_guide.md
            +-- returns markdown string
  |
  v
Browser
  +-- receives {ok: true, markdown: "..."}
  +-- marked.parse(markdown)        Markdown -> HTML (math spans protected)
  +-- KaTeX renderMathInElement()   $...$ and $$...$$ -> rendered math
  +-- swaps to display screen, shows rendered guide
```

The Markdown file is also served separately at `GET /study-guide.md`
so it can be linked, downloaded, or re-rendered without regenerating.

### chunks.json schema

The digital pipeline (`src/chunk.py`) writes one record per overlapping chunk:

```json
[
  {
    "chunk_id":    0,
    "doc_id":      0,
    "source_file": "lecture1.pdf",
    "source_type": "pdf",
    "page":        1,
    "text":        "...",
    "char_start":  0,
    "char_end":    900,
    "source":      "lecture1.pdf"
  }
]
```

`sources.json` carries one entry per unique source file:

```json
[{"title": "lecture1.pdf", "type": "pdf"}]
```

The handwritten pipeline writes `handwritten_chunks.json` with a richer
shape (`chunk_type: "handwritten"`, `citation`, plus extracted
`topics`/`formulas`/`worked_steps`/etc.); `chunks_to_text()` and
`chunks_to_sources()` know how to read both shapes transparently.

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
| `POST` | `/api/upload-notes` | Upload + auto-process raw note files |
| `GET`  | `/api/notes-status` | Check if processed notes exist |

### `GET /api/quiz-stream` query params

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `topic` | string | required | Subject to quiz on |
| `difficulty` | string | `Intermediate` | `Beginner` / `Intermediate` / `Advanced` |
| `numQuestions` | int | `10` | `5`, `10`, or `15` |

Notes mode is selected automatically when processed notes are available;
otherwise the agent falls back to web search. There is no `useNotes` flag.

### `POST /api/generate-study-guide` body (JSON)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `topic` | string | yes | What the cheat sheet is about |
| `grade_level` | string | yes | e.g. `College Sophomore` |
| `major_or_class_level` | string | yes | e.g. `CS, Data Structures` |
| `notes` | string | no | Freeform notes. If omitted/empty, processed notes from the pipeline are auto-loaded. |

Response: `{"ok": true, "markdown": "<full markdown>"}`. The same
markdown is saved to `notes/outputs/study_guide.md`.

### `POST /api/upload-notes` (multipart form)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | string | yes | `digital` or `handwritten` |
| `files` | file(s) | yes | One or more uploaded files (input name `files`) |

Allowed extensions:

| `kind`        | Allowed                          |
|---------------|----------------------------------|
| `digital`     | `.txt` `.md` `.pdf` `.docx`      |
| `handwritten` | `.pdf` `.png` `.jpg` `.jpeg`     |

Response:

```json
{
  "ok": true,
  "saved":   ["lecture1.pdf"],
  "skipped": [{"name": "image.gif", "reason": "unsupported extension .gif"}],
  "processed": {"pages": 17},
  "process_error": null
}
```

For handwritten uploads, `processed` is `{"files": N, "pages": N, "chunks": N}`.
Files are saved before the pipeline runs, so even if `process_error` is
non-null, the raw files are on disk.

### `GET /api/notes-status`

```json
{"available": true, "chunk_count": 54, "source_count": 1}
```

Counts come from the combined digital + handwritten chunks.

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

- **Shared theme**: `static/style.css` is the single source of truth for
  the UI palette, typography (Inter + Fraunces + JetBrains Mono), and
  component styles. Light by default, dark via `prefers-color-scheme`.
- **Study guide markdown viewer** styles are scoped to `.markdown-view`
  inside `study_guide.html` so they don't clash with the form/loading
  screens or the quiz UI.
- **LaTeX math** in study guides uses `$...$` (inline) and `$$...$$` (display).
  The viewer registers a `marked` extension that protects math spans from
  Markdown parsing so underscores, asterisks, and backslashes inside math
  reach KaTeX intact.
- **Semantic color spans** in study guide markdown:
  `key`, `warn`, `tip`, `heading`, `subheading`, `label`. Defined in
  `study_guide.html`'s scoped CSS with dark-mode variants.
- **Notes upload UI**: both `quiz.html` and `study_guide.html` expose the
  same two upload groups (digital + handwritten) plus a status badge that
  reads from `/api/notes-status`. Each Upload button POSTs as
  `multipart/form-data` to `/api/upload-notes` and shows pipeline output
  ("Saved 1 file(s), processed 17 page(s)") in the status line. Handwritten
  uploads warn upfront that the vision pipeline can take a minute since
  each page hits the OpenAI vision API. The status badge re-fetches after
  a successful upload so the chunk count updates immediately.
- **Inline notes paste** (study guide only): the textarea on the study
  guide form is now an optional override. If you paste anything, it wins.
  If you leave it blank, the backend auto-loads whatever's in the processed
  notes pipeline.

---

## Written Analysis

Cramly is an AI study tool that turns a student’s own class material into quizzes and study guides. We realized that students already use AI to study, but most of the time they have to manually explain the class, paste notes, and ask the right prompts to get useful output. We wanted to make that process more automatic.

The main goal was to take whatever material a student already has like typed notes, PDFs, review sheets, or handwritten math work and turn it into something they can actually study from. Instead of only giving a generic explanation of a topic, Cramly reads the uploaded material, breaks it into chunks, adds outside context using Tavily research, and then generates a quiz or study guide based on that combined context.

A big design decision was separating the note processing pipelines. Typed notes are handled with normal text extraction and chunking, while handwritten or math heavy notes use GPT-4o Vision because regular OCR struggles with graphs, equations, and worked-out problems. After both pipelines run, the chunks are merged together so the quiz and study guide generators can use all of the student’s material in one place.

We also added Tavily through an MCP research pipeline to make the output stronger. Before generation, the system can search for relevant sources, extract useful web content, and save that as additional chunks. This means the LLM is not only relying on its general knowledge, it can use the student’s notes, handwritten work, and external context available to make a tailored study quide or quiz.

Challenges & Limitations
**Dependence on note quality and structure**
- The system is highly influenced by the quality of uploaded notes. Well-organized lecture notes produce strong and focused study material, but messy handwriting, incomplete slides, or unclear scans can lead to missing or less accurate concepts being reflected in quizzes or summaries.
**Processing time for large or handwritten uploads**
- While the system aims for immediacy, large PDFs or handwritten documents can introduce noticeable delays because they need to be fully processed before they can be used. This tradeoff was made to ensure accuracy, but it can affect responsiveness for heavier workloads.
**Limited understanding across multiple uploads**
- Each upload is treated independently, meaning the system does not yet build a long-term learning memory across different sessions or subjects. As a result, personalization is strong within a single session, but not fully continuous over time.
**Reduced effectiveness for highly visual subjects**
- The system is strongest with text-based learning. Subjects that rely heavily on diagrams, graphs, or spatial reasoning are not always captured well through text extraction alone, which can limit how complete the generated study material feels.
