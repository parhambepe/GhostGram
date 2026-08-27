"""Real web search with no API key (Bing HTML scrape + DuckDuckGo fallback).

Why this module exists
----------------------
The original implementation relied on Gemini's `google_search` grounding tool,
which is NOT available on many free Google AI plans / `*-flash-lite` models.
So we perform an actual HTTP search and hand clean text snippets to Gemini for
summarization, using only the Python standard library (no bs4 / requests).

Public API
----------
- `web_search.search(query)`         -> (results, error)
- `web_search.search_async(query)`   -> (results, error)   [awaitable]
- `format_context(results)`          -> compact text block for the LLM

`main.py` imports the singleton object (`from web_search import web_search,
format_context`), so the object wrapper below MUST stay in place; the plain
functions are kept as well for backwards compatibility.
"""

import asyncio
import gzip
import html
import re
import urllib.error
import urllib.parse
import urllib.request
import zlib

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "close",
}


def _clean(text: str) -> str:
    """Strip tags/entities and collapse whitespace."""
    txt = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", txt).strip()


def _http_get(url: str, timeout: int = 15) -> str:
    """GET a URL and return decoded HTML (handles gzip/deflate)."""
    req = urllib.request.Request(url, headers=BASE_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        enc = (resp.headers.get("Content-Encoding") or "").lower()
    if "gzip" in enc:
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    elif "deflate" in enc:
        try:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        except Exception:
            pass
    return raw.decode("utf-8", "ignore")


def _unwrap_ddg_url(url: str) -> str:
    """DuckDuckGo wraps result links in /l/?uddg=<encoded> redirects."""
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if "uddg=" in url:
        try:
            qs = urllib.parse.urlparse(url).query
            target = urllib.parse.parse_qs(qs).get("uddg", [""])[0]
            if target:
                return target
        except Exception:
            pass
    return url


# ----------------------------------------------------------------------
# Engines
# ----------------------------------------------------------------------
def _search_bing(query: str, max_results: int = 5, timeout: int = 15):
    """Scrape Bing's `li.b_algo` result blocks (Persian market results)."""
    url = (
        "https://www.bing.com/search?q="
        + urllib.parse.quote(query)
        + "&setlang=fa-IR&mkt=fa-IR"
    )
    page = _http_get(url, timeout)

    out = []
    blocks = re.findall(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', page, re.S)
    for blk in blocks[:max_results]:
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", blk, re.S)
        p = re.search(r"<p[^>]*>(.*?)</p>", blk, re.S)
        a = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"', blk, re.S)
        title = _clean(h2.group(1)) if h2 else ""
        snippet = _clean(p.group(1)) if p else ""
        link = a.group(1) if a else ""
        if title or snippet:
            out.append({"title": title, "snippet": snippet, "url": link})
    return out


def _search_duckduckgo(query: str, max_results: int = 5, timeout: int = 15):
    """Fallback: DuckDuckGo HTML endpoints (no JS, no API key)."""
    endpoints = (
        "https://html.duckduckgo.com/html/?kl=wt-wt&q=",
        "https://lite.duckduckgo.com/lite/?q=",
    )
    for base in endpoints:
        try:
            page = _http_get(base + urllib.parse.quote(query), timeout)
        except Exception:
            continue

        out = []

        # html.duckduckgo.com layout
        titles = re.findall(
            r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            page,
            re.S,
        )
        snippets = re.findall(
            r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', page, re.S
        )
        for i, (link, title) in enumerate(titles[:max_results]):
            snippet = _clean(snippets[i]) if i < len(snippets) else ""
            out.append(
                {
                    "title": _clean(title),
                    "snippet": snippet,
                    "url": _unwrap_ddg_url(link),
                }
            )

        # lite.duckduckgo.com layout
        if not out:
            lite = re.findall(
                r'<a[^>]*class="[^"]*result-link[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                page,
                re.S,
            )
            lite_snips = re.findall(
                r'<td[^>]*class="[^"]*result-snippet[^"]*"[^>]*>(.*?)</td>', page, re.S
            )
            for i, (link, title) in enumerate(lite[:max_results]):
                snippet = _clean(lite_snips[i]) if i < len(lite_snips) else ""
                out.append(
                    {
                        "title": _clean(title),
                        "snippet": snippet,
                        "url": _unwrap_ddg_url(link),
                    }
                )

        out = [r for r in out if r["title"] or r["snippet"]]
        if out:
            return out
    return []


# ----------------------------------------------------------------------
# Public functions
# ----------------------------------------------------------------------
def search(query: str, max_results: int = 5, timeout: int = 15):
    """Blocking search.

    Returns `(results, error)` where results is a list of
    `{"title", "snippet", "url"}` dicts and error is None on success.
    """
    query = (query or "").strip()
    if not query:
        return [], "EmptyQuery: no search terms provided"

    errors = []
    for engine_name, engine in (("bing", _search_bing), ("duckduckgo", _search_duckduckgo)):
        try:
            results = engine(query, max_results, timeout)
            if results:
                return results, None
            errors.append(f"{engine_name}: no results parsed")
        except Exception as e:  # network error, block page, timeout...
            errors.append(f"{engine_name}: {type(e).__name__}: {e}")

    return [], " | ".join(errors) or "no results"


async def search_async(query: str, max_results: int = 5, timeout: int = 15):
    """Async wrapper so the Telethon event loop is never blocked."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: search(query, max_results, timeout)
    )


def format_context(results, max_chars: int = 2500) -> str:
    """Flatten search results into a compact text block for the LLM."""
    if not results:
        return ""
    lines = []
    total = 0
    for i, r in enumerate(results, 1):
        title = (r.get("title") or "").strip()
        snippet = (r.get("snippet") or "").strip()
        url = (r.get("url") or "").strip()
        block = f"[{i}] {title}\n{snippet}".strip()
        if url:
            block += f"\n({url})"
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)
    return "\n\n".join(lines)


class WebSearch:
    """Object facade kept because `main.py` imports the `web_search` singleton."""

    @staticmethod
    def search(query: str, max_results: int = 5, timeout: int = 15):
        return search(query, max_results, timeout)

    @staticmethod
    async def search_async(query: str, max_results: int = 5, timeout: int = 15):
        return await search_async(query, max_results, timeout)

    @staticmethod
    def format_context(results, max_chars: int = 2500) -> str:
        return format_context(results, max_chars)


# Global singleton used by main.py
web_search = WebSearch()
