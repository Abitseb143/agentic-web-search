import os
import textwrap
import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

# --- LLM: Anthropic (Claude) ---
import anthropic

# -----------------------------
# Env + clients
# -----------------------------
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GSEARCH_API_KEY   = os.getenv("GSEARCH_API_KEY")
SEARCH_ENGINE_ID  = os.getenv("SEARCH_ENGINE_ID")

if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY missing in .env")
if not (GSEARCH_API_KEY and SEARCH_ENGINE_ID):
    raise RuntimeError("Google search keys missing in .env (GSEARCH_API_KEY, SEARCH_ENGINE_ID)")

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# -----------------------------
# Web search + fetch
# -----------------------------
def google_search(query: str, num_results: int = 5):
    """Use Google Custom Search API to get top results."""
    service = build("customsearch", "v1", developerKey=GSEARCH_API_KEY)
    res = service.cse().list(q=query, cx=SEARCH_ENGINE_ID, num=num_results).execute()
    return res.get("items", [])

def fetch_text(url: str, max_chars: int = 20_000) -> str:
    """Fetch page and return readable text (trimmed)."""
    try:
        html = requests.get(url, timeout=12).text
        soup = BeautifulSoup(html, "html.parser")

        # Remove script/style
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        # Normalize whitespace
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return text[:max_chars]
    except Exception as e:
        return f"[Fetch error for {url}: {e}]"

# -----------------------------
# LLM call (Claude)
# -----------------------------
def summarize_with_claude(sources: list[dict], user_query: str) -> str:
    """
    sources: list of { 'title': str, 'link': str, 'content': str }
    user_query: the question to answer
    """
    # Build a compact, cited context Claude can work with
    # Keep it lean to avoid token waste; Claude 3.5 Sonnet has a large context window, but trimming is good practice.
    context_blocks = []
    for i, s in enumerate(sources, start=1):
        block = textwrap.dedent(f"""
        [Source {i}]
        Title: {s.get('title') or 'Untitled'}
        URL: {s.get('link')}
        Excerpt:
        {s.get('content', '')[:4000]}
        """).strip()
        context_blocks.append(block)

    context = "\n\n".join(context_blocks)

    system_prompt = (
        "You are a careful research assistant. "
        "Answer the user query using only the information from the provided sources when possible. "
        "Cite sources inline like [1], [2] where you use them. If something isn't supported by the sources, say so."
    )

    user_prompt = textwrap.dedent(f"""
    user_query: {user_query}

    Here are web sources. Use them to produce a concise, well-structured answer with citations:

    {context}
    """).strip()

    msg = claude.messages.create(
        model="claude-3-5-sonnet-latest",   # or "claude-3-5-haiku-latest" for cheaper/faster
        max_tokens=1200,
        temperature=0.2,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Anthropic returns a list of content blocks; join text parts
    parts = []
    for p in msg.content:
        if p.type == "text":
            parts.append(p.text)
    return "".join(parts)

# -----------------------------
# Agent pipeline
# -----------------------------
def agentic_search(query: str, k: int = 5) -> str:
    print(f"🔎 Searching: {query}")
    results = google_search(query, num_results=k)
    if not results:
        return "No search results returned. Check your Google CSE settings (entire web, API enabled)."

    sources = []
    for r in results:
        link = r.get("link")
        title = r.get("title")
        print(f"📎 Fetching: {title} — {link}")
        content = fetch_text(link)
        sources.append({"title": title, "link": link, "content": content})

    print("🤖 Asking Claude...")
    return summarize_with_claude(sources, query)

# -----------------------------
# Entry
# -----------------------------
if __name__ == "__main__":
    q = input("Enter your query: ")
    answer = agentic_search(q, k=5)
    print("\n🧾 Final Answer\n" + "-"*40)
    print(answer)
