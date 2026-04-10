"""Thin wrapper around the Firecrawl API.

This module isolates Firecrawl access behind a small functional interface so
the rest of the codebase doesn't need to know about the SDK. It exposes:

* :func:`is_enabled` — checks whether ``FIRECRAWL_API_KEY`` is set.
* :func:`scrape_url` — fetch one page as clean markdown.
* :func:`scrape_many` — fetch a list of URLs in parallel and return their
  markdown joined with source attribution.
* :func:`map_domain` — enumerate URLs on a domain (cheap discovery).
* :func:`discover_policy_urls` — convenience helper that maps a domain and
  filters the results down to URLs that look like legal/policy pages.

All Firecrawl errors are caught and surfaced as ``FirecrawlError`` so callers
can fall back to the legacy Trafilatura/Playwright pipeline gracefully.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRAPE_TIMEOUT_MS = 30_000
MAX_PARALLEL_SCRAPES = 6
MAX_MARKDOWN_PER_PAGE = 100_000

# Path-fragment regexes that almost always indicate a legal/policy page.
POLICY_URL_PATTERNS = [
    r"/terms",
    r"/tos\b",
    r"/legal",
    r"/privacy",
    r"/dpa\b",
    r"/policies",
    r"/policy",
    r"/acceptable-use",
    r"/aup\b",
    r"/usage",
    r"/ai-policy",
    r"/content-policy",
    r"/community-guidelines",
    r"/copyright",
    r"/ip-",
    r"/intellectual-property",
    r"/eula",
    r"/license",
    r"/sla\b",
    r"/conditions",
    r"/imprint",
]

# Compiled once for performance.
_POLICY_RE = re.compile("|".join(POLICY_URL_PATTERNS), re.IGNORECASE)


class FirecrawlError(Exception):
    """Raised when Firecrawl is misconfigured or returns an error."""


# ---------------------------------------------------------------------------
# Client construction
# ---------------------------------------------------------------------------
_client = None


def is_enabled() -> bool:
    """Return True if a Firecrawl API key is configured."""
    return bool(os.getenv("FIRECRAWL_API_KEY"))


def _get_client():
    """Lazily construct and cache the Firecrawl SDK client."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise FirecrawlError("FIRECRAWL_API_KEY is not set")

    try:
        # The official SDK exposes ``FirecrawlApp`` as the main entrypoint.
        from firecrawl import FirecrawlApp
    except ImportError as exc:
        raise FirecrawlError(
            "firecrawl-py is not installed — run `pip install firecrawl-py`"
        ) from exc

    _client = FirecrawlApp(api_key=api_key)
    return _client


def reset_client() -> None:
    """Drop the cached client (used by tests and config-reload paths)."""
    global _client
    _client = None


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------
def _extract_markdown(result) -> str:
    """Pull the ``markdown`` field out of a Firecrawl scrape result.

    The SDK has shipped a few different return shapes over its lifetime — this
    helper handles dicts, attribute objects, and the ``data``-wrapped variant.
    """
    if result is None:
        return ""
    # Dict-style response
    if isinstance(result, dict):
        if "markdown" in result and result["markdown"]:
            return result["markdown"]
        data = result.get("data")
        if isinstance(data, dict) and data.get("markdown"):
            return data["markdown"]
        return ""
    # Attribute-style response
    md = getattr(result, "markdown", None)
    if md:
        return md
    data = getattr(result, "data", None)
    if data is not None:
        return getattr(data, "markdown", "") or (
            data.get("markdown", "") if isinstance(data, dict) else ""
        )
    return ""


def scrape_url(url: str) -> str:
    """Fetch a single URL via Firecrawl and return its markdown.

    Raises :class:`FirecrawlError` if the API call fails or the response is
    empty so the caller can fall back to the legacy extraction pipeline.
    """
    client = _get_client()
    try:
        result = client.scrape(
            url,
            formats=["markdown"],
            only_main_content=True,
            timeout=SCRAPE_TIMEOUT_MS,
        )
    except Exception as exc:  # pragma: no cover - network failure path
        raise FirecrawlError(f"Firecrawl scrape failed for {url}: {exc}") from exc

    markdown = _extract_markdown(result)
    if not markdown:
        raise FirecrawlError(f"Firecrawl returned no markdown for {url}")
    return markdown[:MAX_MARKDOWN_PER_PAGE]


def scrape_many(urls: list[str]) -> list[dict]:
    """Scrape several URLs in parallel.

    Returns a list of ``{"url", "markdown", "error"}`` dicts (one per input
    URL, in the same order). Failures are captured per-URL rather than
    raising — callers decide whether a partial result is acceptable.
    """
    if not urls:
        return []

    results: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_SCRAPES, len(urls))) as ex:
        future_to_url = {ex.submit(_safe_scrape, u): u for u in urls}
        for fut in as_completed(future_to_url):
            url = future_to_url[fut]
            results[url] = fut.result()

    # Preserve original order
    return [results[u] for u in urls]


def _safe_scrape(url: str) -> dict:
    """Scrape one URL and capture any error inline."""
    try:
        markdown = scrape_url(url)
        return {"url": url, "markdown": markdown, "error": None}
    except FirecrawlError as exc:
        return {"url": url, "markdown": "", "error": str(exc)}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def map_domain(url: str, search: str = "") -> list[str]:
    """Return every URL Firecrawl can find on the given domain.

    The optional ``search`` argument is passed through to Firecrawl's ``/map``
    endpoint, which uses it as a relevance hint when ranking results.
    """
    client = _get_client()
    try:
        result = client.map(url, search=search) if search else client.map(url)
    except Exception as exc:  # pragma: no cover - network failure path
        raise FirecrawlError(f"Firecrawl map failed for {url}: {exc}") from exc

    return _extract_urls(result)


def _extract_urls(result) -> list[str]:
    """Pull the URL list out of a Firecrawl ``/map`` response."""
    if result is None:
        return []
    if isinstance(result, list):
        return [u for u in result if isinstance(u, str)]
    if isinstance(result, dict):
        for key in ("links", "urls", "data"):
            val = result.get(key)
            if isinstance(val, list):
                return [u for u in val if isinstance(u, str)]
        return []
    # Attribute-style
    for attr in ("links", "urls", "data"):
        val = getattr(result, attr, None)
        if isinstance(val, list):
            return [u for u in val if isinstance(u, str)]
    return []


def filter_policy_urls(urls: list[str], domain: str = "") -> list[str]:
    """Filter a URL list down to ones that look like legal/policy pages.

    If ``domain`` is provided, off-domain URLs are dropped first.
    """
    out: list[str] = []
    seen: set[str] = set()
    for u in urls:
        if not isinstance(u, str) or not u.startswith(("http://", "https://")):
            continue
        if domain:
            netloc = urlparse(u).netloc
            if domain not in netloc:
                continue
        if u in seen:
            continue
        if _POLICY_RE.search(u):
            seen.add(u)
            out.append(u)
    return out


def discover_policy_urls(url: str, max_results: int = 8) -> list[str]:
    """Map a domain and return the most likely policy URLs.

    This is the workhorse for the "Other (deep discovery)" UX path: the user
    pastes any URL on a vendor's site, we enumerate the domain via Firecrawl
    ``/map``, and we hand back the URLs that look like terms/privacy/AUP/etc.
    """
    parsed = urlparse(url)
    domain = parsed.netloc
    if not domain:
        raise FirecrawlError(f"Could not parse domain from {url}")

    # Search hint nudges Firecrawl's ranking toward legal pages.
    all_urls = map_domain(url, search="terms privacy policy legal")
    candidates = filter_policy_urls(all_urls, domain=domain)

    # Always include the user's original URL first if it isn't already in the list
    if url not in candidates:
        candidates.insert(0, url)

    return candidates[:max_results]
