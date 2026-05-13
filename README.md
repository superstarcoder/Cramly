# Cramly — AI Study Quiz

An AI-powered quiz generator that creates interactive quizzes either from the
web (DuckDuckGo search) or from a student's own uploaded notes. Built with
OpenAI `gpt-4o-mini`, Flask, and vanilla JS.

---

## Project structure

```
FinalProject/
├── main.py                    # Flask server — all HTTP endpoints
├── pyproject.toml             # Python dependencies
├── .env.example               # Copy to .env and add OPENAI_API_KEY
│
├── src/
│   ├── generate_quiz.py       # Quiz AI agent (Notes mode + Search mode)
│   ├── utils.py               # Helpers: load_chunks, load_sources, chunks_to_text
│   ├── ingest.py              # [TODO groupmate] raw file → text (steps 4-5)
│   ├── chunk.py               # [TODO groupmate] text → chunks.json (step 6)
│   ├── generate_study_guide.py# [TODO] study guide generation
│   ├── mcp_research.py        # [TODO] MCP research utilities
│   └── cite.py                # [TODO] citation formatting
│
├── prompts/
│   ├── quiz_prompt.txt        # Notes-mode quiz prompt template (<<placeholders>>)
│   ├── search_prompt.txt      # Search-mode quiz prompt template
│   └── study_guide_prompt.txt # Study guide prompt template (stub)
│
├── notes/
│   ├── raw/                   # Drop uploaded note files here (PDF, PNG, DOCX)
│   ├── processed/             # Pipeline writes chunks.json + sources.json here
│   └── outputs/               # Generated quiz.json + study_guide.md saved here
│
└── static/
    ├── index.html             # 4-screen SPA (input → agent → quiz → results)
    ├── quiz.js                # All frontend logic and SSE client
    └── style.css              # Dark study-mode theme
```

---

## Architecture

The quiz feature has two generation modes, selected at request time:

**Notes mode** (`useNotes=true`)
> User's processed notes are read from `notes/processed/chunks.json` and
> passed directly to GPT as context. No web search. Fast (single API call).
> Requires the notes pipeline (steps 4-6) to have run first.

**Search mode** (`useNotes=false`, default)
> GPT runs a tool-use loop, calling DuckDuckGo to find textbook summaries,
> Quizlet cards, interview questions, and practice problems. Slower (4-6
> searches), but works without any notes.

---

## Code flow

### Notes mode

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

### Search mode

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

Open <http://localhost:5000> in your browser.

To use a different port:
```bash
PORT=8080 python main.py
```

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the quiz UI |
| `GET` | `/api/quiz-stream` | SSE stream of agent events |
| `POST` | `/api/generate-quiz` | Blocking quiz generation |
| `POST` | `/api/evaluate-answer` | Grade a short-answer response |
| `GET` | `/api/notes-status` | Check if processed notes exist |

### `GET /api/quiz-stream` query params

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `topic` | string | required | Subject to quiz on |
| `difficulty` | string | `Intermediate` | `Beginner` / `Intermediate` / `Advanced` |
| `numQuestions` | int | `10` | `5`, `10`, or `15` |
| `useNotes` | bool | `false` | Generate from `notes/processed/` instead of web |

### SSE event types

| `type` | Fields | When |
|--------|--------|------|
| `notes_loaded` | `message`, `char_count` | Notes mode: notes read into context |
| `search_start` | `query` | Search mode: agent begins a search |
| `search_done` | `query`, `count`, `titles` | Search mode: results received |
| `generating` | `message` | GPT is writing the quiz JSON |
| `complete` | `quiz` | Quiz object is ready |
| `error` | `message` | Something went wrong |
