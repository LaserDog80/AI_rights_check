"""Local cache for scraped Terms & Conditions text.

Every time the app successfully scrapes T&C content for a domain, the text
is saved here with a timestamp.  On subsequent analyses the cached version
can be served instantly — no network round-trip required.

Cache layout (JSON, one file per domain):

    cached_tocs/
        midjourney.com.json
        openai.com.json
        ...

Each file:

    {
      "domain": "midjourney.com",
      "last_updated": "2026-04-10T06:45:00Z",
      "pages": [
        {
          "url": "https://docs.midjourney.com/...",
          "title": "Terms of Service",
          "text": "...",
          "scraped_at": "2026-04-10T06:45:00Z"
        }
      ],
      "combined_text": "..."
    }
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

CACHE_DIR = Path(__file__).resolve().parent.parent / "cached_tocs"


def _domain_key(url: str) -> str:
    """Normalise a URL to a cache-safe domain key."""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    domain = domain.lstrip("www.")
    # Sanitise for filesystem
    return re.sub(r"[^a-zA-Z0-9._-]", "_", domain)


def _cache_path(domain_key: str) -> Path:
    return CACHE_DIR / f"{domain_key}.json"


def get(url: str) -> dict | None:
    """Return cached T&C data for *url*'s domain, or ``None``."""
    key = _domain_key(url)
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save(url: str, combined_text: str, pages_crawled: list[dict]) -> None:
    """Persist scraped T&C content for *url*'s domain."""
    key = _domain_key(url)
    now = datetime.now(timezone.utc).isoformat()

    pages = []
    for p in pages_crawled:
        pages.append({
            "url": p.get("url", ""),
            "title": p.get("type", ""),
            "text_length": p.get("text_length", 0),
            "scraped_at": now,
        })

    record = {
        "domain": key,
        "last_updated": now,
        "pages": pages,
        "combined_text": combined_text,
    }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_cache_path(key), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def save_analysis(url: str, mode: str, result: dict) -> None:
    """Cache an LLM analysis result (summary, deep, tier-compare) for a domain.

    Stored alongside the raw T&C text in the same cache file under an
    ``analyses`` dict keyed by mode.
    """
    key = _domain_key(url)
    path = _cache_path(key)
    now = datetime.now(timezone.utc).isoformat()

    record: dict = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                record = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    if "analyses" not in record:
        record["analyses"] = {}

    record["analyses"][mode] = {
        "result": result,
        "analysed_at": now,
    }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def get_analysis(url: str, mode: str) -> dict | None:
    """Return a cached LLM analysis result for *url*'s domain + mode, or ``None``."""
    key = _domain_key(url)
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entry = data.get("analyses", {}).get(mode)
        if entry and entry.get("result"):
            return entry
        return None
    except (json.JSONDecodeError, OSError):
        return None


def list_cached() -> list[dict]:
    """Return summary metadata for every cached domain."""
    if not CACHE_DIR.exists():
        return []
    results = []
    for path in sorted(CACHE_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            results.append({
                "domain": data.get("domain", path.stem),
                "last_updated": data.get("last_updated", ""),
                "page_count": len(data.get("pages", [])),
                "text_length": len(data.get("combined_text", "")),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return results
