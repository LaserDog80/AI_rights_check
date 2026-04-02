"""AI-assisted multi-page web crawl for T&C discovery."""

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .extraction import HEADERS, MAX_TEXT_LENGTH, fetch_terms_text
from .analysis import get_client

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
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        landing_html = resp.text
    except requests.RequestException as e:
        return {"combined_text": "", "pages_crawled": [], "page_count": 0,
                "error": f"Failed to fetch landing page: {e}"}

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
