"""One-shot script to crawl all known sites via Firecrawl and populate the cache."""

import os
import sys

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from src.known_sites import KNOWN_SITES
from src import firecrawl_client
from src.toc_cache import save

print(f"Firecrawl enabled: {firecrawl_client.is_enabled()}")
if not firecrawl_client.is_enabled():
    print("ERROR: FIRECRAWL_API_KEY not set in .env")
    sys.exit(1)

print(f"Sites to crawl: {len(KNOWN_SITES)}\n")

results = {}
for slug, site in KNOWN_SITES.items():
    name = site["name"]
    urls = site.get("urls", [])
    print(f"--- {name} ({len(urls)} URLs) ---")

    try:
        scraped = firecrawl_client.scrape_many(urls)
        pages = []
        parts = []
        for item in scraped:
            url = item.get("url", "")
            md = item.get("markdown", "")
            err = item.get("error")
            if err:
                print(f"  FAIL: {url} -> {err}")
            elif md and len(md) > 100:
                print(f"  OK:   {url} ({len(md)} chars)")
                pages.append({"url": url, "type": "policy/terms page", "text_length": len(md)})
                parts.append(f"=== SOURCE: {url} ===\n\n{md}")
            else:
                print(f"  SKIP: {url} (too short: {len(md)} chars)")

        combined = "\n\n---\n\n".join(parts)
        if combined:
            save(urls[0], combined, pages)
            results[slug] = {"status": "OK", "pages": len(pages), "chars": len(combined)}
        else:
            results[slug] = {"status": "EMPTY", "pages": 0, "chars": 0}
            print(f"  ** No content scraped for {name}")
    except Exception as e:
        results[slug] = {"status": "ERROR", "error": str(e)}
        print(f"  ** ERROR: {e}")
    print()

print("=" * 60)
print("SUMMARY")
print("=" * 60)
ok = sum(1 for r in results.values() if r["status"] == "OK")
fail = sum(1 for r in results.values() if r["status"] != "OK")
print(f"Succeeded: {ok}/{len(results)}")
print(f"Failed:    {fail}/{len(results)}")
print()
for slug, r in results.items():
    status = r["status"]
    if status == "OK":
        print(f"  + {slug}: {r['pages']} pages, {r['chars']} chars")
    else:
        print(f"  x {slug}: {status} - {r.get('error', 'no content')}")
