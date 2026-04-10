"""Run all three analysis modes for every known site and cache the results."""

import os
import json
import time

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from src.known_sites import KNOWN_SITES
from src.analysis import analyse_terms, deep_analyse_terms, tier_compare_terms, get_client
from src import toc_cache

# Verify LLM is configured
try:
    client, model = get_client()
    print(f"LLM: {model}")
except Exception as e:
    print(f"ERROR: LLM not configured: {e}")
    exit(1)

sites = list(KNOWN_SITES.items())
modes = ["summary", "deep", "tier-compare"]
total = len(sites) * len(modes)
done = 0
errors = []

print(f"Sites: {len(sites)} | Modes: {len(modes)} | Total analyses: {total}\n")

for slug, site in sites:
    name = site["name"]

    # Find the cached T&C text for this site
    urls = site.get("urls", [])
    cached = None
    for u in urls:
        cached = toc_cache.get(u)
        if cached and cached.get("combined_text"):
            cache_url = u
            break

    if not cached or not cached.get("combined_text"):
        print(f"--- {name}: SKIP (no cached T&C text) ---")
        errors.append((slug, "all", "no cached T&C text"))
        done += 3
        continue

    text = cached["combined_text"]
    text_len = len(text)

    # Truncate if extremely long to avoid token limits
    if text_len > 120000:
        text = text[:120000]

    print(f"--- {name} ({text_len} chars) ---")

    # 1. Summary
    done += 1
    existing = toc_cache.get_analysis(cache_url, "summary")
    if existing:
        print(f"  [{done}/{total}] Summary: already cached")
    else:
        try:
            print(f"  [{done}/{total}] Summary: analysing...", end="", flush=True)
            result = analyse_terms(text)
            result["source_url"] = name
            result["text_length"] = text_len
            result["terms_fetched_at"] = cached.get("last_updated", "")
            toc_cache.save_analysis(cache_url, "summary", result)
            print(f" done ({result.get('classification', '?')})")
        except Exception as e:
            print(f" ERROR: {e}")
            errors.append((slug, "summary", str(e)))

    # 2. Deep (clause-by-clause)
    done += 1
    existing = toc_cache.get_analysis(cache_url, "deep")
    if existing:
        print(f"  [{done}/{total}] Deep: already cached")
    else:
        try:
            print(f"  [{done}/{total}] Deep: analysing...", end="", flush=True)
            result = deep_analyse_terms(text)
            result["source_url"] = name
            result["text_length"] = text_len
            result["terms_fetched_at"] = cached.get("last_updated", "")
            toc_cache.save_analysis(cache_url, "deep", result)
            clauses = len(result.get("clauses", []))
            print(f" done ({clauses} clauses)")
        except Exception as e:
            print(f" ERROR: {e}")
            errors.append((slug, "deep", str(e)))

    # 3. Tier compare
    done += 1
    existing = toc_cache.get_analysis(cache_url, "tier-compare")
    if existing:
        print(f"  [{done}/{total}] Tier compare: already cached")
    else:
        try:
            print(f"  [{done}/{total}] Tier compare: analysing...", end="", flush=True)
            result = tier_compare_terms(text)
            result["source_url"] = name
            result["text_length"] = text_len
            result["terms_fetched_at"] = cached.get("last_updated", "")
            toc_cache.save_analysis(cache_url, "tier-compare", result)
            tiers = len(result.get("tiers_detected", []))
            print(f" done ({tiers} tiers)")
        except Exception as e:
            print(f" ERROR: {e}")
            errors.append((slug, "tier-compare", str(e)))

    print()

print("=" * 60)
print("COMPLETE")
print("=" * 60)
print(f"Analysed: {done - len(errors)*1}/{total}")
if errors:
    print(f"\nErrors ({len(errors)}):")
    for slug, mode, err in errors:
        print(f"  x {slug} [{mode}]: {err}")
else:
    print("No errors!")
