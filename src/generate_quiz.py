"""
generate_quiz.py
================
Abstract:
    Core AI agent for Cramly's interactive quiz feature. Supports two modes:

      • Notes mode  — generates questions from user-provided study notes
                      (processed text from the ingest → chunk pipeline).
                      No web search; GPT reads the notes directly as context.
      • Search mode — the original behaviour: DuckDuckGo web searches feed
                      GPT's tool-use loop, which generates questions from results.

    Mode is selected by the caller: pass notes_text to generate_quiz_stream()
    for Notes mode; omit it to fall back to Search mode.

Code Flow (Notes mode):
    1. generate_quiz_stream(topic, difficulty, num_questions, notes_text) called.
    2. notes_text embedded in prompt from prompts/quiz_prompt.txt.
    3. Single GPT call generates quiz JSON — no tool-use loop.
    4. Events yielded: notes_loaded → generating → complete.

Code Flow (Search mode):
    1. generate_quiz_stream(topic, difficulty, num_questions) called.
    2. Prompt from prompts/search_prompt.txt starts the tool-use loop.
    3. GPT calls search_web; DuckDuckGo runs; results fed back to GPT.
    4. Events yielded: search_start → search_done (×N) → generating → complete.
"""

import json
import os
import pathlib
import re

from duckduckgo_search import DDGS
from openai import OpenAI


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "prompts"
MODEL = "gpt-4o-mini"
MAX_SEARCHES = 10
# Truncate notes to this length to stay well within GPT's context window.
MAX_NOTES_CHARS = 50_000

SYSTEM_PROMPT = (
    "You are an expert educational quiz creator and AI study agent. "
    "Your goal is to help students prepare for exams and technical interviews. "
    "When given study notes, base all questions strictly on the provided content. "
    "When searching the web, gather accurate, current information before writing "
    "any questions. Document your reasoning about what concepts you found and why "
    "you made the question choices you did — this transparency helps students "
    "understand how the quiz was constructed."
)

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": (
            "Search the internet for information about a topic. "
            "Use this to find textbook summaries, Quizlet study sets, "
            "online tutorials, interview question banks, and practice problems."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "The search query, e.g. "
                        "'time series analysis key concepts textbook'"
                    )
                }
            },
            "required": ["query"]
        }
    }
}


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _fill(template: str, **kwargs) -> str:
    """Replace <<key>> placeholders. Safe with JSON curly braces in templates."""
    for key, val in kwargs.items():
        template = template.replace(f"<<{key}>>", str(val))
    return template


def _build_notes_prompt(topic: str, difficulty: str, num_questions: int, notes_text: str) -> str:
    num_mc = max(1, round(num_questions * 0.5))
    num_tf = max(1, round(num_questions * 0.3))
    num_sa = max(1, num_questions - num_mc - num_tf)
    return _fill(
        _load_prompt("quiz_prompt.txt"),
        topic=topic,
        difficulty=difficulty,
        num_questions=num_questions,
        num_mc=num_mc,
        num_tf=num_tf,
        num_sa=num_sa,
        notes_text=notes_text[:MAX_NOTES_CHARS],
    )


def _build_search_prompt(topic: str, difficulty: str, num_questions: int) -> str:
    num_mc = max(1, round(num_questions * 0.5))
    num_tf = max(1, round(num_questions * 0.3))
    num_sa = max(1, num_questions - num_mc - num_tf)
    return _fill(
        _load_prompt("search_prompt.txt"),
        topic=topic,
        difficulty=difficulty,
        num_questions=num_questions,
        num_mc=num_mc,
        num_tf=num_tf,
        num_sa=num_sa,
    )


# ---------------------------------------------------------------------------
# DuckDuckGo search helper (Search mode only)
# ---------------------------------------------------------------------------

def _execute_search(query: str) -> tuple[list, str]:
    """Run a DuckDuckGo search. Returns (results_list, json_string)."""
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=5))
        results = [
            {
                "title":   r.get("title", ""),
                "url":     r.get("href", ""),
                "snippet": r.get("body", "")
            }
            for r in raw
        ]
        return results, json.dumps(results, indent=2)
    except Exception as exc:
        error_payload = [{"error": str(exc)}]
        return error_payload, json.dumps(error_payload)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class QuizGenerator:
    """
    AI agent that generates structured quizzes.
    Supports two modes: Notes (no web search) and Search (DuckDuckGo tool loop).
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. "
                "Copy .env.example to .env and add your key."
            )
        self.client = OpenAI(api_key=api_key)

    # ------------------------------------------------------------------
    # Public: streaming interface (used by the SSE endpoint)
    # ------------------------------------------------------------------

    def generate_quiz_stream(
        self,
        topic: str,
        difficulty: str,
        num_questions: int,
        notes_text: str | None = None,
        sources: list | None = None,
    ):
        """
        Generator that yields structured events as the quiz is built.

        Event shapes:
          {"type": "notes_loaded", "message": str, "char_count": int}
          {"type": "search_start", "query": str}
          {"type": "search_done",  "query": str, "count": int, "titles": [str]}
          {"type": "generating",   "message": str}
          {"type": "complete",     "quiz": dict}
          {"type": "error",        "message": str}
        """
        if notes_text:
            yield from self._stream_from_notes(
                topic, difficulty, num_questions, notes_text, sources or []
            )
        else:
            yield from self._stream_from_search(topic, difficulty, num_questions)

    # ------------------------------------------------------------------
    # Public: blocking interface (fallback POST endpoint)
    # ------------------------------------------------------------------

    def generate_quiz(
        self,
        topic: str,
        difficulty: str,
        num_questions: int,
        notes_text: str | None = None,
        sources: list | None = None,
    ) -> dict:
        """
        Blocking wrapper around generate_quiz_stream.
        Consumes all events and returns only the final quiz dict.
        """
        for event in self.generate_quiz_stream(
            topic, difficulty, num_questions, notes_text, sources
        ):
            if event["type"] == "complete":
                return event["quiz"]
            if event["type"] == "error":
                raise RuntimeError(event["message"])
        raise RuntimeError("Stream ended without a quiz.")

    def evaluate_short_answer(
        self,
        question: str,
        model_answer: str,
        key_points: list,
        student_answer: str,
    ) -> dict:
        """
        Grade a student's short-answer response using GPT.

        Returns a dict: { "score": "correct|partial|incorrect",
                          "feedback": "<1-2 sentence evaluation>" }
        """
        key_points_text = "\n".join(f"- {p}" for p in (key_points or []))

        prompt = f"""Evaluate a student's answer to the following short-answer question.

Question: {question}

Model Answer: {model_answer}

Key Points to Cover:
{key_points_text or "(none specified)"}

Student's Answer: {student_answer}

Return ONLY a JSON object (no markdown, no extra text):
{{
  "score": "correct|partial|incorrect",
  "feedback": "1-2 sentences of specific, constructive feedback"
}}

Scoring guide:
  correct   — covers the main concepts and shows clear understanding
  partial   — shows some understanding but misses one or more key points
  incorrect — fundamentally wrong, irrelevant, or shows no real understanding"""

        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$",       "", raw, flags=re.MULTILINE)

        try:
            result = json.loads(raw.strip())
            if result.get("score") not in ("correct", "partial", "incorrect"):
                result["score"] = "partial"
            return result
        except (json.JSONDecodeError, KeyError):
            return {
                "score": "partial",
                "feedback": (
                    "Your answer was received but could not be auto-graded. "
                    "Compare your response with the model answer below."
                ),
            }

    # ------------------------------------------------------------------
    # Private: Notes mode
    # ------------------------------------------------------------------

    def _stream_from_notes(
        self,
        topic: str,
        difficulty: str,
        num_questions: int,
        notes_text: str,
        sources: list,
    ):
        """Generate a quiz using provided notes text — no web search required."""
        char_count = min(len(notes_text), MAX_NOTES_CHARS)
        yield {
            "type":       "notes_loaded",
            "message":    f"Loaded {char_count:,} characters of notes",
            "char_count": char_count,
        }

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role":    "user",
                "content": _build_notes_prompt(topic, difficulty, num_questions, notes_text),
            },
        ]

        try:
            yield {"type": "generating", "message": "Composing your quiz from notes..."}

            response = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.3,
            )
            quiz = self._parse_quiz(response.choices[0].message.content)

            # Merge sources from notes pipeline if the quiz didn't populate them.
            if sources and not quiz.get("sources"):
                quiz["sources"] = sources

            yield {"type": "complete", "quiz": quiz}

        except Exception as exc:
            yield {"type": "error", "message": str(exc)}

    # ------------------------------------------------------------------
    # Private: Search mode (original behaviour)
    # ------------------------------------------------------------------

    def _stream_from_search(self, topic: str, difficulty: str, num_questions: int):
        """Generate a quiz using DuckDuckGo web searches (original behaviour)."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role":    "user",
                "content": _build_search_prompt(topic, difficulty, num_questions),
            },
        ]

        try:
            for _ in range(MAX_SEARCHES):
                response = self.client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=[SEARCH_TOOL],
                    tool_choice="auto",
                    temperature=0.3,
                )

                message       = response.choices[0].message
                finish_reason = response.choices[0].finish_reason

                if finish_reason == "stop":
                    yield {"type": "generating", "message": "Composing your quiz questions..."}
                    quiz = self._parse_quiz(message.content)
                    yield {"type": "complete", "quiz": quiz}
                    return

                if finish_reason == "tool_calls":
                    messages.append(message)

                    for tool_call in message.tool_calls:
                        query = json.loads(tool_call.function.arguments).get("query", "")

                        yield {"type": "search_start", "query": query}

                        results_list, results_json = _execute_search(query)
                        titles = [
                            r["title"] for r in results_list
                            if isinstance(r, dict) and r.get("title")
                        ][:3]

                        yield {
                            "type":   "search_done",
                            "query":  query,
                            "count":  len(results_list),
                            "titles": titles,
                        }

                        messages.append({
                            "role":         "tool",
                            "tool_call_id": tool_call.id,
                            "content":      results_json,
                        })

            yield {
                "type":    "error",
                "message": (
                    f"Agent reached {MAX_SEARCHES} searches without finishing. "
                    "Try a more specific topic."
                ),
            }

        except Exception as exc:
            yield {"type": "error", "message": str(exc)}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_quiz(self, raw: str) -> dict:
        """Extract and parse the JSON quiz from GPT's response text."""
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```\s*$",       "", text, flags=re.MULTILINE)
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse quiz JSON: {exc}\n\n"
                f"First 500 chars of GPT response:\n{raw[:500]}"
            )
