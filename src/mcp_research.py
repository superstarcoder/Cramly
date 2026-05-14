"""
mcp_research.py
===============
Research layer that uses the Tavily MCP server (via an MCP client) to fetch
high-quality external sources for a topic.

Architecture:
    Cramly Flask app
      → Python MCP client  (mcp library)
      → Tavily MCP server  (subprocess: npx -y tavily-mcp@latest)
      → tavily-search      → snippets from quality sources
      → tavily-extract     → full page content from top URLs
      → external_chunks.json (picked up by load_all_note_chunks())

Requires:
    - Node.js ≥ 18 + npx  (for the Tavily MCP server subprocess)
    - TAVILY_API_KEY in .env
    - pip install mcp

Output:
    notes/processed/external_sources.json
    notes/processed/external_chunks.json

CLI:
    python -m src.mcp_research --topic "joint pdf" --grade "college" --major "statistics"
"""

import argparse
import asyncio
import json
import os
import re
from collections import Counter
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROCESSED_DIR = Path(__file__).parent.parent / "notes" / "processed"

# ---------------------------------------------------------------------------
# Source quality control
# ---------------------------------------------------------------------------

QUALITY_DOMAINS = [
    "khanacademy.org",
    "libretexts.org",
    "ocw.mit.edu",
    "statlect.com",
    "brilliant.org",
    "tutorial.math.lamar.edu",
    "opentext.bc.ca",
    "stat.yale.edu",
    "probabilitycourse.com",
    "mathworld.wolfram.com",
    "wikipedia.org",
    "openstax.org",
    "math.stackexchange.com",
    "stats.stackexchange.com",
]

EXCLUDE_DOMAINS = [
    "chegg.com",
    "coursehero.com",
    "studocu.com",
    "bartleby.com",
    "homeworklib.com",
    "numerade.com",
    "clutchprep.com",
]

MAX_EXTRACT_URLS     = 3   # URLs to full-extract per query
MAX_RESULTS_PER_QUERY = 5


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _save_json(path: str | Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Query builder — driven by note chunk content
# ---------------------------------------------------------------------------

def build_research_queries(
    topic: str,
    note_chunks: list[dict] | None = None,
    grade_level: str | None = None,
    major: str | None = None,
    max_queries: int = 4,
) -> list[str]:
    """
    Build targeted search queries from the student's actual note content.

    Extracts the most frequent meaningful terms from the notes so queries
    reflect what the student is actually studying, not just the generic topic.
    """
    level = grade_level or "university"

    note_keywords: list[str] = []
    if note_chunks:
        sample = " ".join(c.get("text", "")[:400] for c in note_chunks[:8])
        words = [w.lower() for w in sample.split() if len(w) > 5 and w.isalpha()]
        note_keywords = [w for w, _ in Counter(words).most_common(6)]

    kw1 = " ".join(note_keywords[:2]) if note_keywords else (major or "").strip()
    kw2 = " ".join(note_keywords[2:4]) if len(note_keywords) > 2 else "practice problems"

    queries = [
        f"{topic} {kw1} worked examples step by step",
        f"{topic} {kw2} solutions explained",
        f"{topic} {level} lecture notes",
        f"{topic} common mistakes misconceptions",
    ]
    return queries[:max_queries]


# ---------------------------------------------------------------------------
# MCP result parsers
# ---------------------------------------------------------------------------

def _parse_text_blocks(text: str) -> list[dict]:
    """
    Parse the plain-text format returned by the Tavily MCP server.

    Each result block looks like:
        Title: <title>
        URL:   <url>
        Content: <snippet text …>
        Raw Content: <full page text …>   ← only present in extract responses

    Blocks are delimited by the next 'Title:' line or end-of-string.
    """
    blocks = re.split(r"\n(?=Title: )", text)
    results = []
    for block in blocks:
        title_m = re.search(r"^Title: (.+)", block, re.MULTILINE)
        url_m   = re.search(r"^URL: (.+)",   block, re.MULTILINE)
        if not (title_m and url_m):
            continue
        raw_m  = re.search(r"^Raw Content: (.*)", block, re.MULTILINE | re.DOTALL)
        cont_m = re.search(r"^Content: (.*?)(?=\nRaw Content:|\Z)", block, re.MULTILINE | re.DOTALL)
        content = (raw_m.group(1) if raw_m else (cont_m.group(1) if cont_m else "")).strip()
        if content.lower() == "undefined":
            content = ""
        results.append({
            "title": title_m.group(1).strip(),
            "url":   url_m.group(1).strip(),
            "text":  content,
        })
    return results


def _parse_search_result(resp) -> list[dict]:
    """Parse a CallToolResult from tavily_search into a list of source dicts."""
    try:
        text = resp.content[0].text
        # New versions return plain text; fall back to JSON for older builds.
        try:
            raw = json.loads(text)
            items = raw.get("results", raw) if isinstance(raw, dict) else raw
            return [
                {"title": r.get("title", ""), "url": r.get("url", ""), "text": r.get("content", "")}
                for r in (items if isinstance(items, list) else [])
                if r.get("url")
            ]
        except json.JSONDecodeError:
            return [r for r in _parse_text_blocks(text) if r.get("url")]
    except Exception as exc:
        print(f"  [mcp] search parse error: {exc}")
        return []


def _parse_extract_result(resp) -> dict[str, str]:
    """Parse a CallToolResult from tavily_extract into a {url: full_text} map."""
    try:
        text = resp.content[0].text
        try:
            raw = json.loads(text)
            items = raw.get("results", raw) if isinstance(raw, dict) else raw
            return {
                r["url"]: r.get("raw_content") or r.get("content", "")
                for r in (items if isinstance(items, list) else [])
                if r.get("url")
            }
        except json.JSONDecodeError:
            return {r["url"]: r["text"] for r in _parse_text_blocks(text) if r.get("url")}
    except Exception as exc:
        print(f"  [mcp] extract parse error: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Async MCP client — connects to Tavily MCP server subprocess
# ---------------------------------------------------------------------------

async def _research_async(
    queries: list[str],
    max_results: int = MAX_RESULTS_PER_QUERY,
) -> list[dict]:
    """
    Open one MCP session to the Tavily MCP server and run all queries.

    For each query:
      1. Call tavily-search  → get snippets from quality-filtered sources
      2. Call tavily-extract → replace snippets with full page content
                               for the top MAX_EXTRACT_URLS URLs
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "tavily-mcp@latest"],
        env={**os.environ, "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", "")},
    )

    all_sources: list[dict] = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            for query in queries:
                print(f"  [mcp] search: {query!r}")

                # ── Step 1: search ───────────────────────────────────────────
                search_resp = await session.call_tool("tavily_search", {
                    "query":          query,
                    "max_results":    max_results,
                    "include_domains": QUALITY_DOMAINS,
                    "exclude_domains": EXCLUDE_DOMAINS,
                })
                results = _parse_search_result(search_resp)
                print(f"    → {len(results)} result(s)")

                # ── Step 2: extract full content from top URLs ───────────────
                top_urls = [r["url"] for r in results if r.get("url")][:MAX_EXTRACT_URLS]
                if top_urls:
                    print(f"  [mcp] extract: {len(top_urls)} URL(s)")
                    extract_resp = await session.call_tool("tavily_extract", {
                        "urls": top_urls,
                    })
                    extracted = _parse_extract_result(extract_resp)
                    # Upgrade snippet → full page text where available
                    for r in results:
                        if r["url"] in extracted and extracted[r["url"]]:
                            r["text"] = extracted[r["url"]]

                for r in results:
                    r["query"] = query
                all_sources.extend(results)

    return all_sources


# ---------------------------------------------------------------------------
# Chunk builder — enriched citation metadata
# ---------------------------------------------------------------------------

def source_to_external_chunk(source: dict, index: int) -> dict:
    chunk_id = f"web_chunk_{index:03d}"
    text = source.get("text") or source.get("snippet") or source.get("title", "")
    return {
        "chunk_id":    chunk_id,
        "chunk_type":  "external",
        "source_type": "web",
        "title":       source.get("title", ""),
        "url":         source.get("url", ""),
        "provider":    "tavily-mcp",
        "query":       source.get("query", ""),
        "text":        text,
        "citation": {
            "title":        source.get("title", ""),
            "url":          source.get("url", ""),
            "provider":     "tavily-mcp",
            "retrieved_at": date.today().isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def research_with_mcp(
    topic: str,
    grade_level: str | None = None,
    major: str | None = None,
    max_results: int = MAX_RESULTS_PER_QUERY,
) -> dict:
    """
    Run the full MCP research pipeline for a topic.

    Connects to a Tavily MCP server subprocess (requires npx + Node.js),
    performs targeted search + full-content extraction, and saves:
        notes/processed/external_sources.json
        notes/processed/external_chunks.json

    Gracefully skips if TAVILY_API_KEY is not set or the MCP server fails.
    Returns {"queries": int, "sources": int, "chunks": int}.
    """
    if not os.getenv("TAVILY_API_KEY"):
        print("  [mcp] TAVILY_API_KEY not set — skipping web research.")
        return {"queries": 0, "sources": 0, "chunks": 0}

    # Import here to avoid circular dependency (utils imports nothing from here)
    from src.utils import load_all_note_chunks
    note_chunks = [c for c in load_all_note_chunks() if c.get("chunk_type") != "external"]

    queries = build_research_queries(topic, note_chunks, grade_level, major)
    print(f"\nMCP research: {topic!r} — {len(queries)} queries via Tavily MCP server")
    for q in queries:
        print(f"  • {q}")

    try:
        all_sources = asyncio.run(_research_async(queries, max_results))
    except Exception as exc:
        print(f"  [mcp] MCP session failed: {exc}")
        print("  [mcp] Ensure Node.js ≥ 18 and npx are installed.")
        return {"queries": len(queries), "sources": 0, "chunks": 0}

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[dict] = []
    for s in all_sources:
        url = s.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(s)

    external_chunks = [source_to_external_chunk(s, i) for i, s in enumerate(unique)]

    _save_json(PROCESSED_DIR / "external_sources.json", unique)
    _save_json(PROCESSED_DIR / "external_chunks.json", external_chunks)

    print(f"\n  → {len(unique)} source(s), {len(external_chunks)} chunk(s) saved.")
    return {"queries": len(queries), "sources": len(unique), "chunks": len(external_chunks)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MCP research for a topic.")
    parser.add_argument("--topic",  required=True, help="Topic to research")
    parser.add_argument("--grade",  default=None,  help="Grade level, e.g. 'college'")
    parser.add_argument("--major",  default=None,  help="Major or subject, e.g. 'statistics'")
    parser.add_argument("--max",    type=int, default=MAX_RESULTS_PER_QUERY,
                        help="Max search results per query")
    args = parser.parse_args()

    result = research_with_mcp(
        topic=args.topic,
        grade_level=args.grade,
        major=args.major,
        max_results=args.max,
    )
    print(
        f"\nDone — {result['queries']} queries, "
        f"{result['sources']} source(s), "
        f"{result['chunks']} chunk(s)"
    )
    print("  sources → notes/processed/external_sources.json")
    print("  chunks  → notes/processed/external_chunks.json")
