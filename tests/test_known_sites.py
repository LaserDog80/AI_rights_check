"""Tests for src.known_sites — curated platform registry."""

import unittest

from src.known_sites import (
    KNOWN_SITES,
    CATEGORY_DIRECT,
    CATEGORY_AGGREGATOR,
    CATEGORY_AVATAR,
    get_site,
    list_sites,
)


class TestKnownSitesRegistry(unittest.TestCase):
    def test_expected_platforms_present(self):
        """Spot-check the platforms the user explicitly requested."""
        for slug in [
            "midjourney", "runway", "pika", "luma", "sora", "google_flow",
            "kling", "minimax", "dreamina", "grok", "ideogram", "leonardo",
            "firefly", "recraft", "flux",
            "freepik", "krea", "openart", "weavy", "fal",
            "hedra", "heygen", "synthesia",
        ]:
            assert slug in KNOWN_SITES, f"Missing platform: {slug}"

    def test_all_entries_have_required_fields(self):
        for slug, entry in KNOWN_SITES.items():
            assert "name" in entry, f"{slug} missing name"
            assert "category" in entry, f"{slug} missing category"
            assert "urls" in entry, f"{slug} missing urls"
            assert isinstance(entry["urls"], list), f"{slug} urls not a list"
            assert len(entry["urls"]) > 0, f"{slug} has no URLs"
            for url in entry["urls"]:
                assert url.startswith("https://"), f"{slug} non-https URL: {url}"

    def test_aggregators_have_stacked_terms_note(self):
        for slug, entry in KNOWN_SITES.items():
            if entry["category"] == CATEGORY_AGGREGATOR:
                assert entry.get("stacked_terms_note"), \
                    f"Aggregator {slug} missing stacked_terms_note"
                assert entry.get("underlying_models"), \
                    f"Aggregator {slug} missing underlying_models"


class TestGetSite(unittest.TestCase):
    def test_returns_known_slug(self):
        site = get_site("midjourney")
        assert site is not None
        assert site["name"] == "Midjourney"
        assert site["category"] == CATEGORY_DIRECT

    def test_returns_none_for_unknown(self):
        assert get_site("nonexistent_platform") is None

    def test_aggregator_lookup(self):
        site = get_site("freepik")
        assert site is not None
        assert site["category"] == CATEGORY_AGGREGATOR
        assert "Flux" in site["underlying_models"]


class TestListSites(unittest.TestCase):
    def test_returns_all_sites(self):
        sites = list_sites()
        assert len(sites) == len(KNOWN_SITES)

    def test_groups_by_category(self):
        sites = list_sites()
        categories_seen = []
        for s in sites:
            if not categories_seen or categories_seen[-1] != s["category"]:
                categories_seen.append(s["category"])
        # Direct should come before aggregators which come before avatars
        if CATEGORY_DIRECT in categories_seen and CATEGORY_AGGREGATOR in categories_seen:
            assert categories_seen.index(CATEGORY_DIRECT) < categories_seen.index(CATEGORY_AGGREGATOR)
        if CATEGORY_AGGREGATOR in categories_seen and CATEGORY_AVATAR in categories_seen:
            assert categories_seen.index(CATEGORY_AGGREGATOR) < categories_seen.index(CATEGORY_AVATAR)

    def test_aggregator_flag(self):
        sites = list_sites()
        freepik = next(s for s in sites if s["slug"] == "freepik")
        assert freepik["is_aggregator"] is True
        midjourney = next(s for s in sites if s["slug"] == "midjourney")
        assert midjourney["is_aggregator"] is False

    def test_each_site_has_dropdown_fields(self):
        for s in list_sites():
            assert "slug" in s
            assert "name" in s
            assert "category" in s
            assert "tiers" in s
            assert "is_aggregator" in s


if __name__ == "__main__":
    unittest.main()
