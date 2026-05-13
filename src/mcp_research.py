"""
mcp_research.py
===============
Research layer that uses MCP search/fetch tools to find high-quality
external sources for a topic. Saves citeable chunks that
load_all_note_chunks() picks up alongside regular and handwritten notes.

Output:
  notes/processed/external_sources.json
  notes/processed/external_chunks.json

Run:
  python -m src.mcp_research --topic "joint pdf" --grade "college" --major "statistics"
"""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROCESSED_DIR = Path(__file__).parent.parent / "notes" / "processed"


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def save_json(path: str | Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: str | Path, default=None):
    path = Path(path)
    if not path.exists():
        return default if default is not None else []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default if default is not None else []


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def build_research_queries(
    topic: str,
    grade_level: str | None = None,
    major: str | None = None,
    note_chunks: list[dict] | None = None,
    max_queries: int = 4,
) -> list[str]:
    """
    Build targeted academic search queries for a topic.

    Pulls keywords from existing note chunks when available to add specificity.
    Returns at most max_queries strings.
    """
    level = grade_level or "university"
    field = (major or "").strip()

    queries = [
        f"{topic} explained {level}",
        f"{topic} worked examples",
        f"{topic} {field} tutorial".strip() if field else f"{topic} lecture notes",
        f"{topic} common mistakes practice problems",
    ]

    # Add one chunk-informed query if notes are available
    if note_chunks:
        sample = " ".join(c.get("text", "")[:150] for c in note_chunks[:3])
        keywords = [w for w in sample.split() if len(w) > 5]
        if keywords:
            queries.append(f"{topic} {keywords[0]}")

    return queries[:max_queries]


# ---------------------------------------------------------------------------
# Tavily search (MCP research layer)
# ---------------------------------------------------------------------------

def call_mcp_search_fetch(query: str, max_results: int = 5) -> list[dict]:
    """
    Search for external sources using the Tavily API.

    Requires TAVILY_API_KEY in .env. Get a free key at https://tavily.com.
    Returns a list of source dicts:
        [{"title": str, "url": str, "snippet": str, "provider": str}, ...]
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print(f"  [tavily] TAVILY_API_KEY not set — skipping: {query!r}")
        return []

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=max_results)
        return [
            {
                "title":    r.get("title", ""),
                "url":      r.get("url", ""),
                "snippet":  r.get("content", ""),
                "provider": "tavily",
            }
            for r in response.get("results", [])
        ]
    except Exception as e:
        print(f"  [tavily] Search failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Chunk builder
# ---------------------------------------------------------------------------

def source_to_external_chunk(source: dict, index: int) -> dict:
    """
    Convert a raw source record into a citeable external chunk.

    The chunk_type="external" field is recognised by load_all_note_chunks()
    and chunks_to_sources() in utils.py.
    """
    chunk_id = f"web_chunk_{index:03d}"
    text = source.get("snippet") or source.get("content") or source.get("title", "")
    return {
        "chunk_id":    chunk_id,
        "chunk_type":  "external",
        "source_type": "web",
        "title":       source.get("title", ""),
        "url":         source.get("url", ""),
        "provider":    source.get("provider", "mcp"),
        "query":       source.get("query", ""),
        "text":        text,
        "citation": {
            "title":    source.get("title", ""),
            "url":      source.get("url", ""),
            "provider": source.get("provider", "mcp"),
        },
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def research_with_mcp(
    topic: str,
    grade_level: str | None = None,
    major: str | None = None,
    max_results: int = 5,
) -> dict:
    """
    Run the full MCP research pipeline for a topic.

    Loads existing note chunks for context, builds targeted queries,
    calls the MCP search/fetch tool, deduplicates by URL, then saves:
      notes/processed/external_sources.json
      notes/processed/external_chunks.json

    Returns {"queries": int, "sources": int, "chunks": int}
    """
    print(f"\nMCP research: {topic!r}")

    # Import here to avoid circular imports (utils imports nothing from here)
    from src.utils import load_all_note_chunks
    note_chunks = load_all_note_chunks()

    queries = build_research_queries(topic, grade_level, major, note_chunks)
    print(f"Built {len(queries)} queries:")
    for q in queries:
        print(f"  • {q}")

    all_sources: list[dict] = []
    for query in queries:
        print(f"\nQuerying: {query!r}")
        results = call_mcp_search_fetch(query, max_results=max_results)
        for r in results:
            r["query"] = query
        all_sources.extend(results)
        print(f"  → {len(results)} result(s)")

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique_sources: list[dict] = []
    for s in all_sources:
        url = s.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_sources.append(s)

    external_chunks = [
        source_to_external_chunk(src, i)
        for i, src in enumerate(unique_sources)
    ]

    sources_path = PROCESSED_DIR / "external_sources.json"
    chunks_path  = PROCESSED_DIR / "external_chunks.json"

    save_json(sources_path, unique_sources)
    save_json(chunks_path, external_chunks)

    if not unique_sources:
        print("\nWarning: no external sources found — configure MCP_SERVER_URL in .env.")
    else:
        print(f"\nSaved {len(unique_sources)} source(s) → {sources_path.name}")
        print(f"Saved {len(external_chunks)} chunk(s)  → {chunks_path.name}")

    return {
        "queries": len(queries),
        "sources": len(unique_sources),
        "chunks":  len(external_chunks),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MCP research for a topic.")
    parser.add_argument("--topic", required=True, help="Topic to research")
    parser.add_argument("--grade", default=None,  help="Grade level, e.g. 'college'")
    parser.add_argument("--major", default=None,  help="Major or subject, e.g. 'statistics'")
    parser.add_argument("--max",   type=int, default=5, help="Max results per query")
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
    print(f"  sources: notes/processed/external_sources.json")
    print(f"  chunks:  notes/processed/external_chunks.json")
