# server.py
import os
import textwrap
from typing import List, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dotenv import load_dotenv

# Web + extraction
import requests
import trafilatura
from bs4 import BeautifulSoup

# Google Custom Search
from googleapiclient.discovery import build

# Anthropic (Claude)
import anthropic


# =========================
# Env & clients
# =========================
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GSEARCH_API_KEY   = os.getenv("GSEARCH_API_KEY")
SEARCH_ENGINE_ID  = os.getenv("SEARCH_ENGINE_ID")

if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY missing in .env")
if not (GSEARCH_API_KEY and SEARCH_ENGINE_ID):
    raise RuntimeError("GSEARCH_API_KEY or SEARCH_ENGINE_ID missing in .env")

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Persisted session with desktop UA (helps some sites serve real HTML)
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
})


# =========================
# Schemas
# =========================
class SearchRequest(BaseModel):
    query: str
    k: int = 6  # number of strong sources to keep


class SearchResponse(BaseModel):
    query: str
    answer: str
    sources: List[Dict[str, str]]  # [{title, link}]


# =========================
# Search helpers
# =========================
AUTHORITATIVE_HINTS = [
    "site:wikipedia.org",
    "site:britannica.com",
    "site:new7wonders.com",
    "site:nationalgeographic.com",
    "site:unesco.org",
]

WHITELIST_DOMAINS = (
    "wikipedia.org",
    "britannica.com",
    "new7wonders.com",
    "nationalgeographic.com",
    "unesco.org",
)


def google_search_once(query: str, num_results: int = 10):
    service = build("customsearch", "v1", developerKey=GSEARCH_API_KEY)
    res = service.cse().list(q=query, cx=SEARCH_ENGINE_ID, num=min(num_results, 10)).execute()
    return res.get("items", []) or []


def smart_search(query: str, k: int = 8):
    """
    Try multiple query variants and bias toward authoritative domains.
    Returns a de-duped list of result objects (title/link/snippet...).
    """
    queries = [query, f"{query} official list", f"{query} locations"]
    queries += [f"{query} {hint}" for hint in AUTHORITATIVE_HINTS]

    seen = set()
    items = []
    budget = max(12, k * 2)

    for q in queries:
        results = google_search_once(q, 10)
        for it in results:
            link = it.get("link")
            if not link or link in seen:
                continue
            seen.add(link)
            items.append(it)
            if len(items) >= budget:
                break
        if len(items) >= budget:
            break

    # light quality filter
    good = [it for it in items if it.get("title") and it.get("link")]
    return good[:max(10, k)]


# =========================
# Extraction
# =========================
def fetch_text(url: str, max_chars: int = 30_000) -> str:
    """
    Extract readable text using trafilatura with fallback to BeautifulSoup.
    """
    try:
        # Try trafilatura's own fetch first (it sometimes handles redirects/enc better)
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
            )
            if text and text.strip():
                return text.strip()[:max_chars]

        # Fallback: requests + BeautifulSoup minimal cleanup
        resp = SESSION.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()
        text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
        return text[:max_chars] if text else ""
    except Exception as e:
        return f"[Fetch error for {url}: {e}]"


def strong_sources(results, k: int = 6):
    """
    Keep sources that are on trusted domains or have enough extracted content.
    """
    sources = []
    for r in results:
        link = r.get("link")
        title = r.get("title") or "Untitled"
        if not link:
            continue
        content = fetch_text(link)
        is_whitelisted = any(d in (link or "") for d in WHITELIST_DOMAINS)
        long_enough = content and len(content) >= 800  # rough cut-off for useful pages

        if is_whitelisted or long_enough:
            sources.append({"title": title, "link": link, "content": content})

        if len(sources) >= k:
            break

    return sources


# =========================
# LLM
# =========================
def summarize_with_claude(sources: List[Dict[str, str]], user_query: str) -> str:
    """
    Ask Claude to answer using the provided sources, but allow succinct general-knowledge
    answers for widely accepted facts. Still cite at least one reputable source when possible.
    """
    context_blocks = []
    for i, s in enumerate(sources, start=1):
        block = textwrap.dedent(f"""
        [Source {i}]
        Title: {s.get('title') or 'Untitled'}
        URL: {s.get('link')}
        Excerpt:
        {(s.get('content') or '')[:6000]}
        """).strip()
        context_blocks.append(block)

    context = "\n\n".join(context_blocks)

    system_prompt = (
        "You are a precise research assistant. Prefer answers grounded in the provided sources, "
        "with citations like [1], [2]. If the question concerns widely accepted general facts "
        "(e.g., capitals, well-known lists, definitions) and the provided sources are thin, you may "
        "answer succinctly using general knowledge, but still try to ground with at least one reputable "
        "source from those provided. If essential details truly aren’t in the sources and not reliable "
        "as general knowledge, say what is missing and suggest the single best next source to check."
    )

    user_prompt = f"user_query: {user_query}\n\nSources:\n{context}"

    msg = claude.messages.create(
        model="claude-3-5-sonnet-latest",  # or "claude-3-5-haiku-latest"
        max_tokens=1400,
        temperature=0.2,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    parts = []
    for p in msg.content:
        if getattr(p, "type", "") == "text":
            parts.append(p.text)
    return "".join(parts).strip()


def agentic_search(query: str, k: int = 6):
    # 1) broader + biased search
    results = smart_search(query, k=max(10, k * 2))
    if not results:
        raise HTTPException(status_code=400, detail="No search results. Check Google CSE settings.")

    # 2) filter/strengthen
    sources = strong_sources(results, k=k)
    if not sources:  # final fallback: use top few raw
        sources = [{
            "title": r.get("title", "Untitled"),
            "link": r.get("link"),
            "content": fetch_text(r.get("link"))
        } for r in results[:k]]

    # 3) summarize
    answer = summarize_with_claude(sources, query)

    # return slim sources to client
    return answer, [{"title": s["title"], "link": s["link"]} for s in sources]


# =========================
# FastAPI app
# =========================
app = FastAPI(title="Agentic Search API (Claude)")

# CORS for your Vite dev server(s)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    try:
        answer, slim_sources = agentic_search(req.query, k=req.k)
        return SearchResponse(query=req.query, answer=answer, sources=slim_sources)
    except anthropic.APIStatusError as e:
        # Claude-side failure
        raise HTTPException(status_code=502, detail=f"Claude error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
