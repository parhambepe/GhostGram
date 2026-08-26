"""Real web search via Bing HTML scrape (no API key, works on free tiers).

The previous implementation relied on Gemini's `google_search` grounding tool,
which is NOT available on many free Google AI plans / *-flash-lite models.
This module performs an actual HTTP search against Bing and returns clean
text snippets using only the Python standard library (no bs4 dependency),
which are then fed to Gemini for summarization.
"""

import asyncio
import html
import re
import urllib.parse
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _clean(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _fetch_html(query: str, timeout: int = 15) -> str:
    # Request Persian-market results so Farsi queries return Farsi snippets
    url = "https://www.bing.com/search?q=" + urllib.parse.quote(query) + "&setlang=fa-IR&mkt=fa-IR"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fa-IR,fa;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def _parse_results(page: str, max_results: int = 5):
    """Parse Bing's `li.b_algo` result blocks with regex (no external deps)."""
    out = []
    # Each result block: <li class="b_algo" ...> ... <h2>title</h2> ... <p>snippet</p> ... </li>
    blocks = re.findall(r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>', page, re.S)
    for blk in blocks[:max_results]:
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", blk, re.S)
        # snippet: first <p> inside the block
        p = re.search(r"<p[^>]*>(.*?)</p>", blk, re.S)
        a = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"', blk)
        url = a.group(1) if a else ""
        title = _clean(h2.group(1)) if h2 else ""
        snippet = _clean(p.group(1)) if p else ""
        if title or snippet:
            out.append({"title": title, "snippet": snippet, "url": url})
    return out


def search(query: str, max_results: int = 5, timeout: int = 15):
    """Blocking search (returns list of {title, snippet, url})."""
    try:
        page = _fetch_html(query, timeout)
        results = _parse_results(page, max_results)
        if not results:
            # Fallback: grab any <p> text blocks as crude snippets
            for m in re.findall(r"<p[^>]*>(.*?)</p>", page, re.S)[:max_results]:
                txt = _clean(m)
                if len(txt) > 30:
                    results.append({"title": "", "snippet": txt, "url": ""})
        return results, None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


async def search_async(query: str, max_results: int = 5, timeout: int = 15):
    """Async wrapper so it doesn't block the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: search(query, max_results, timeout))


def format_context(results, max_chars: int = 2500) -> str:
    """Flatten search results into a compact text block for the LLM."""
    if not results:
        return ""
    lines = []
    total = 0
    for i, r in enumerate(results, 1):
        block = f"[{i}] {r['title']}\n{r['snippet']}".strip()
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)
    return "\n\n".join(lines)
