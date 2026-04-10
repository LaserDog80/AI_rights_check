"""AI-assisted multi-page web crawl for T&C discovery."""

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import firecrawl_client
from .extraction import (
    HEADERS, MAX_TEXT_LENGTH, PASTE_OR_UPLOAD_HINT,
    _check_cloudflare, _fetch_html_with_playwright, _extract_text_from_html,
    fetch_terms_text,
)
from .analysis import get_client
from .known_sites import KNOWN_SITES, get_site

MAX_PAGES = 8

# Prompt used to ask the LLM which links are relevant
LINK_DISCOVERY_PROMPT = """\
You are a web navigation assistant. The user will give you a list of links found on \
a website's page. Your job is to identify which links are most likely to lead to:

1. Terms of Service / Terms & Conditions
2. Privacy Policy
3. Acceptable Use Policy
4. Pricing / Plans page (showing tier differences)
5. Enterprise agreements or enterprise terms
6. Data Processing Agreement (DPA)
7. Copyright / IP policy
8. Service Level Agreement (SLA)

Return a JSON object with EXACTLY this schema (no markdown, no code fences, pure JSON):

{
  "relevant_links": [
    {
      "url": "<full URL>",
      "likely_content": "<what this page probably contains>",
      "priority": <1-10, 10 = most relevant>
    }
  ]
}

Rules:
- Only include links that are likely to contain legal terms, policies, or pricing info.
- Maximum 8 links.
- Sort by priority descending.
- If no relevant links are found, return {"relevant_links": []}.
"""


def _extract_links(html: str, base_url: str) -> list[dict]:
    """Extract all links from HTML, resolving relative URLs."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        full_url = urljoin(base_url, href)
        # Only keep links on the same domain
        if urlparse(full_url).netloc != urlparse(base_url).netloc:
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        link_text = a_tag.get_text(strip=True)[:100]
        links.append({"url": full_url, "text": link_text})
    return links


def _ask_llm_for_links(links: list[dict], api_key: str = "", base_url: str = "",
                        model: str = "") -> list[dict]:
    """Use the LLM to identify which links are relevant to T&C analysis."""
    import json

    client, m = get_client(api_key, base_url, model)

    links_text = "\n".join(
        f"- {link['url']} (link text: \"{link['text']}\")" for link in links
    )

    response = client.chat.completions.create(
        model=m,
        messages=[
            {"role": "system", "content": LINK_DISCOVERY_PROMPT},
            {"role": "user", "content": f"Here are the links found on the page:\n\n{links_text}"},
        ],
        temperature=0.1,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    result = json.loads(raw)
    return result.get("relevant_links", [])


def ai_crawl(url: str, api_key: str = "", base_url: str = "",
             model: str = "", progress_callback=None) -> dict:
    """Perform an AI-assisted crawl of a website to gather T&C content.

    Parameters
    ----------
    url : str
        The starting URL to crawl.
    api_key, base_url, model : str
        Optional API configuration for the LLM.
    progress_callback : callable, optional
        Called with (step_description, current_step, total_steps) for progress updates.

    Returns
    -------
    dict
        {"combined_text": str, "pages_crawled": list[dict], "page_count": int}
    """
    pages_crawled = []

    def _report(msg, step, total):
        if progress_callback:
            progress_callback(msg, step, total)

    # Step 1: Fetch the landing page
    _report("Fetching landing page...", 1, 4)
    landing_html = None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        _check_cloudflare(resp)
        resp.raise_for_status()
        landing_html = resp.text
    except (ValueError, requests.RequestException):
        pass

    if landing_html is None:
        _report("Direct fetch failed, trying headless browser...", 1, 4)
        try:
            landing_html = _fetch_html_with_playwright(url)
            if len(_extract_text_from_html(landing_html)) < 100:
                raise ValueError("Not enough content")
        except Exception:
            return {"combined_text": "", "pages_crawled": [], "page_count": 0,
                    "error": (
                        "Could not fetch the landing page, even with a headless"
                        " browser." + PASTE_OR_UPLOAD_HINT
                    )}

    # Step 2: Extract links and ask LLM which are relevant
    _report("Discovering relevant pages with AI...", 2, 4)
    links = _extract_links(landing_html, url)

    if not links:
        # No links found — just extract text from the landing page
        text = fetch_terms_text(url)
        return {
            "combined_text": text,
            "pages_crawled": [{"url": url, "type": "landing page"}],
            "page_count": 1,
        }

    try:
        relevant = _ask_llm_for_links(links, api_key, base_url, model)
    except Exception:
        relevant = []

    # Always include the original URL
    urls_to_crawl = [url]
    seen_urls = {url}
    for link in sorted(relevant, key=lambda x: x.get("priority", 0), reverse=True):
        link_url = link.get("url", "")
        if link_url and link_url not in seen_urls and len(urls_to_crawl) < MAX_PAGES:
            urls_to_crawl.append(link_url)
            seen_urls.add(link_url)

    # Step 3: Crawl each identified page
    _report(f"Crawling {len(urls_to_crawl)} pages...", 3, 4)
    combined_parts = []
    for i, page_url in enumerate(urls_to_crawl):
        try:
            text = fetch_terms_text(page_url)
            if text and len(text) > 100:
                # Find what this page is about from the relevant links list
                likely = "landing page" if page_url == url else "policy/terms page"
                for r in relevant:
                    if r.get("url") == page_url:
                        likely = r.get("likely_content", likely)
                        break
                pages_crawled.append({
                    "url": page_url,
                    "type": likely,
                    "text_length": len(text),
                })
                combined_parts.append(
                    f"=== SOURCE: {page_url} ({likely}) ===\n\n{text}"
                )
        except Exception:
            continue

    # Step 4: Aggregate
    _report("Aggregating content...", 4, 4)
    combined_text = "\n\n---\n\n".join(combined_parts)

    # Cap total text length
    if len(combined_text) > MAX_TEXT_LENGTH * 2:
        combined_text = combined_text[: MAX_TEXT_LENGTH * 2]

    return {
        "combined_text": combined_text,
        "pages_crawled": pages_crawled,
        "page_count": len(pages_crawled),
    }


# ---------------------------------------------------------------------------
# Firecrawl-powered crawl strategies
# ---------------------------------------------------------------------------
def _combine_scraped(scraped: list[dict], max_length: int) -> tuple[str, list[dict]]:
    """Join a list of scrape results into one document with source attribution."""
    parts: list[str] = []
    pages: list[dict] = []
    for item in scraped:
        url = item.get("url", "")
        markdown = item.get("markdown", "")
        if not markdown or len(markdown) < 100:
            continue
        pages.append({
            "url": url,
            "type": "policy/terms page",
            "text_length": len(markdown),
        })
        parts.append(f"=== SOURCE: {url} ===\n\n{markdown}")
    combined = "\n\n---\n\n".join(parts)
    if len(combined) > max_length:
        combined = combined[:max_length]
    return combined, pages


def known_site_crawl(slug: str, progress_callback=None) -> dict:
    """Scrape every URL we have on file for a curated known platform.

    Returns the same dict shape as :func:`ai_crawl` plus a ``known_site``
    metadata block describing the platform, its tiers, and (for aggregators)
    its underlying-model warning.
    """
    site = get_site(slug)
    if not site:
        return {
            "combined_text": "",
            "pages_crawled": [],
            "page_count": 0,
            "error": f"Unknown site slug: {slug}",
        }

    def _report(msg, step, total):
        if progress_callback:
            progress_callback(msg, step, total)

    urls = list(site.get("urls", []))
    if not urls:
        return {
            "combined_text": "",
            "pages_crawled": [],
            "page_count": 0,
            "error": f"No URLs configured for {site.get('name', slug)}",
        }

    _report(f"Scraping {len(urls)} pages for {site['name']}...", 1, 2)

    # Prefer Firecrawl for parallel scraping when available, otherwise fall
    # back to the legacy fetch_terms_text pipeline (sequential).
    if firecrawl_client.is_enabled():
        try:
            scraped = firecrawl_client.scrape_many(urls)
        except Exception as exc:
            return _legacy_known_site_crawl(site, urls, str(exc), _report)
    else:
        return _legacy_known_site_crawl(site, urls, "", _report)

    _report("Aggregating content...", 2, 2)
    combined_text, pages_crawled = _combine_scraped(scraped, MAX_TEXT_LENGTH * 3)

    if not combined_text:
        return {
            "combined_text": "",
            "pages_crawled": [],
            "page_count": 0,
            "error": (
                f"Could not extract text from any of the {len(urls)} configured"
                f" pages for {site['name']}." + PASTE_OR_UPLOAD_HINT
            ),
        }

    return {
        "combined_text": combined_text,
        "pages_crawled": pages_crawled,
        "page_count": len(pages_crawled),
        "known_site": {
            "slug": slug,
            "name": site["name"],
            "category": site.get("category"),
            "tiers": site.get("tiers", []),
            "is_aggregator": site.get("category") == "aggregator",
            "underlying_models": site.get("underlying_models", []),
            "stacked_terms_note": site.get("stacked_terms_note", ""),
            "highlights": site.get("highlights", []),
        },
    }


def _legacy_known_site_crawl(site: dict, urls: list[str], firecrawl_err: str,
                              report) -> dict:
    """Fallback: scrape known-site URLs sequentially via the legacy pipeline."""
    pages_crawled: list[dict] = []
    combined_parts: list[str] = []
    for i, page_url in enumerate(urls):
        report(f"Fetching page {i + 1} of {len(urls)}...", i + 1, len(urls))
        try:
            text = fetch_terms_text(page_url)
            if text and len(text) > 100:
                pages_crawled.append({
                    "url": page_url,
                    "type": "policy/terms page",
                    "text_length": len(text),
                })
                combined_parts.append(f"=== SOURCE: {page_url} ===\n\n{text}")
        except Exception:
            continue

    combined_text = "\n\n---\n\n".join(combined_parts)
    if len(combined_text) > MAX_TEXT_LENGTH * 3:
        combined_text = combined_text[: MAX_TEXT_LENGTH * 3]

    if not combined_text:
        msg = (
            f"Could not extract text from any of the {len(urls)} configured"
            f" pages for {site['name']}."
        )
        if firecrawl_err:
            msg += f" Firecrawl error: {firecrawl_err}."
        return {
            "combined_text": "",
            "pages_crawled": [],
            "page_count": 0,
            "error": msg + PASTE_OR_UPLOAD_HINT,
        }

    return {
        "combined_text": combined_text,
        "pages_crawled": pages_crawled,
        "page_count": len(pages_crawled),
        "known_site": {
            "slug": next(
                (k for k, v in KNOWN_SITES.items() if v is site), ""
            ),
            "name": site["name"],
            "category": site.get("category"),
            "tiers": site.get("tiers", []),
            "is_aggregator": site.get("category") == "aggregator",
            "underlying_models": site.get("underlying_models", []),
            "stacked_terms_note": site.get("stacked_terms_note", ""),
            "highlights": site.get("highlights", []),
        },
    }


# Common T&C path patterns to probe when discovery fails.
_COMMON_TOC_PATHS = [
    "/terms-of-service", "/terms", "/tos", "/legal/terms-of-service",
    "/legal/terms", "/legal", "/privacy", "/privacy-policy",
    "/acceptable-use", "/aup",
    "/docs/terms-of-service", "/docs/privacy-policy",
    "/docs/terms", "/docs/acceptable-use-policy",
]


def _probe_common_toc_urls(url: str, report=None) -> list[str]:
    """Try well-known T&C URL patterns on the domain and its docs. subdomain.

    Returns a list of URLs that responded with a 200 status.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lstrip("www.")
    bases = [
        f"https://{parsed.netloc}",
        f"https://www.{domain}",
        f"https://docs.{domain}",
    ]
    # De-duplicate bases
    bases = list(dict.fromkeys(bases))

    if report:
        report("Probing common T&C URL patterns...", 1, 3)

    found: list[str] = []
    seen: set[str] = set()
    use_firecrawl = firecrawl_client.is_enabled()

    for base in bases:
        for path in _COMMON_TOC_PATHS:
            probe_url = base + path
            if probe_url in seen:
                continue
            seen.add(probe_url)
            try:
                resp = requests.get(probe_url, headers=HEADERS, timeout=8,
                                    allow_redirects=True)
                # Accept 200, or 403 when Firecrawl can bypass bot protection
                if resp.status_code not in (200, 403):
                    continue
                if resp.status_code == 403 and not use_firecrawl:
                    continue
                final_url = resp.url
                if final_url in seen:
                    continue
                seen.add(final_url)
                found.append(final_url)
            except requests.RequestException:
                continue
            if len(found) >= MAX_PAGES:
                return found
    return found


def firecrawl_discovery_crawl(url: str, progress_callback=None,
                              api_key: str = "", base_url: str = "",
                              model: str = "") -> dict:
    """Deep-discovery crawl for an unknown site via Firecrawl ``/map``.

    Strategy:
    1. Map the entire domain (cheap, no page fetches).
    2. Filter the URL list down to ones that look like legal/policy pages.
    3. Scrape the top N candidates in parallel.
    4. Combine into a single document with source attribution.

    Falls back to :func:`ai_crawl` if Firecrawl is not configured.
    """
    def _report(msg, step, total):
        if progress_callback:
            progress_callback(msg, step, total)

    _ai_crawl_kwargs = dict(
        api_key=api_key, base_url=base_url, model=model,
        progress_callback=progress_callback,
    )

    if not firecrawl_client.is_enabled():
        # No Firecrawl key — use the existing LLM-driven crawler
        return ai_crawl(url, **_ai_crawl_kwargs)

    _report("Mapping domain to discover policy pages...", 1, 3)
    try:
        candidates = firecrawl_client.discover_policy_urls(url, max_results=MAX_PAGES)
    except firecrawl_client.FirecrawlError:
        # Map failed — fall back to LLM-driven crawl
        return ai_crawl(url, **_ai_crawl_kwargs)

    # If map only returned the original URL (no actual policy pages found),
    # try common T&C URL patterns before falling back to the LLM crawler.
    if not candidates or candidates == [url]:
        probed = _probe_common_toc_urls(url, _report)
        if probed:
            candidates = probed
        else:
            return ai_crawl(url, **_ai_crawl_kwargs)

    _report(f"Scraping {len(candidates)} discovered pages...", 2, 3)
    try:
        scraped = firecrawl_client.scrape_many(candidates)
    except Exception as exc:
        return {
            "combined_text": "",
            "pages_crawled": [],
            "page_count": 0,
            "error": (
                f"Firecrawl scrape failed during discovery: {exc}."
                + PASTE_OR_UPLOAD_HINT
            ),
        }

    _report("Aggregating content...", 3, 3)
    combined_text, pages_crawled = _combine_scraped(scraped, MAX_TEXT_LENGTH * 3)

    if not combined_text:
        # Nothing usable from /map results — try the LLM crawler as a last resort
        return ai_crawl(url, **_ai_crawl_kwargs)

    return {
        "combined_text": combined_text,
        "pages_crawled": pages_crawled,
        "page_count": len(pages_crawled),
        "discovery_method": "firecrawl_map",
        "candidates_found": len(candidates),
    }
