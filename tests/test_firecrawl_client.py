"""Tests for src.firecrawl_client — Firecrawl API wrapper."""

import os
import unittest
from unittest.mock import MagicMock, patch

from src import firecrawl_client


class TestIsEnabled(unittest.TestCase):
    def test_enabled_when_key_set(self):
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-test"}):
            assert firecrawl_client.is_enabled() is True

    def test_disabled_when_key_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            assert firecrawl_client.is_enabled() is False


class TestExtractMarkdown(unittest.TestCase):
    def test_dict_with_markdown(self):
        result = firecrawl_client._extract_markdown({"markdown": "# Hello"})
        assert result == "# Hello"

    def test_dict_with_data_wrapper(self):
        result = firecrawl_client._extract_markdown({"data": {"markdown": "# Wrapped"}})
        assert result == "# Wrapped"

    def test_object_with_markdown_attr(self):
        obj = MagicMock()
        obj.markdown = "# Object"
        # Avoid the .data attribute fallback being a MagicMock
        obj.data = None
        result = firecrawl_client._extract_markdown(obj)
        assert result == "# Object"

    def test_returns_empty_for_none(self):
        assert firecrawl_client._extract_markdown(None) == ""

    def test_returns_empty_when_no_markdown(self):
        assert firecrawl_client._extract_markdown({"other": "field"}) == ""


class TestExtractUrls(unittest.TestCase):
    def test_list_input(self):
        urls = ["https://a.com", "https://b.com"]
        assert firecrawl_client._extract_urls(urls) == urls

    def test_dict_with_links_key(self):
        result = {"links": ["https://a.com", "https://b.com"]}
        assert firecrawl_client._extract_urls(result) == ["https://a.com", "https://b.com"]

    def test_dict_with_urls_key(self):
        result = {"urls": ["https://x.com"]}
        assert firecrawl_client._extract_urls(result) == ["https://x.com"]

    def test_empty_input(self):
        assert firecrawl_client._extract_urls(None) == []
        assert firecrawl_client._extract_urls({}) == []


class TestFilterPolicyUrls(unittest.TestCase):
    def test_keeps_policy_urls(self):
        urls = [
            "https://example.com/terms",
            "https://example.com/privacy-policy",
            "https://example.com/blog/post-1",
            "https://example.com/legal/dpa",
            "https://example.com/about",
        ]
        result = firecrawl_client.filter_policy_urls(urls, domain="example.com")
        assert "https://example.com/terms" in result
        assert "https://example.com/privacy-policy" in result
        assert "https://example.com/legal/dpa" in result
        assert "https://example.com/blog/post-1" not in result
        assert "https://example.com/about" not in result

    def test_filters_off_domain_when_specified(self):
        urls = [
            "https://example.com/terms",
            "https://other.com/terms",
        ]
        result = firecrawl_client.filter_policy_urls(urls, domain="example.com")
        assert result == ["https://example.com/terms"]

    def test_deduplicates(self):
        urls = ["https://example.com/terms", "https://example.com/terms"]
        result = firecrawl_client.filter_policy_urls(urls)
        assert len(result) == 1

    def test_drops_non_http(self):
        urls = ["mailto:a@b.com", "javascript:void(0)", "https://example.com/terms"]
        result = firecrawl_client.filter_policy_urls(urls)
        assert result == ["https://example.com/terms"]


class TestScrapeUrl(unittest.TestCase):
    """Tests that bypass the real Firecrawl SDK by patching ``_get_client``."""

    def setUp(self):
        firecrawl_client.reset_client()

    def tearDown(self):
        firecrawl_client.reset_client()

    def test_scrape_returns_markdown(self):
        mock_app = MagicMock()
        mock_app.scrape_url.return_value = {"markdown": "# Terms\n\nFull text here..." * 30}
        with patch.object(firecrawl_client, "_get_client", return_value=mock_app):
            result = firecrawl_client.scrape_url("https://example.com/terms")
            assert "# Terms" in result

    def test_scrape_raises_on_empty(self):
        mock_app = MagicMock()
        mock_app.scrape_url.return_value = {"markdown": ""}
        with patch.object(firecrawl_client, "_get_client", return_value=mock_app):
            with self.assertRaises(firecrawl_client.FirecrawlError):
                firecrawl_client.scrape_url("https://example.com/terms")

    def test_scrape_raises_when_disabled(self):
        # When the SDK is missing AND no key is set, _get_client raises.
        with patch.dict(os.environ, {}, clear=True):
            firecrawl_client.reset_client()
            with self.assertRaises(firecrawl_client.FirecrawlError):
                firecrawl_client.scrape_url("https://example.com/terms")


class TestScrapeMany(unittest.TestCase):
    def setUp(self):
        firecrawl_client.reset_client()

    def tearDown(self):
        firecrawl_client.reset_client()

    def test_scrape_many_preserves_order(self):
        mock_app = MagicMock()

        def fake_scrape(url, **kwargs):
            return {"markdown": f"# Content from {url}\n\n" + ("text " * 50)}

        mock_app.scrape_url.side_effect = fake_scrape
        with patch.object(firecrawl_client, "_get_client", return_value=mock_app):
            urls = [
                "https://example.com/a",
                "https://example.com/b",
                "https://example.com/c",
            ]
            results = firecrawl_client.scrape_many(urls)
            assert len(results) == 3
            for i, url in enumerate(urls):
                assert results[i]["url"] == url
                assert results[i]["error"] is None
                assert url in results[i]["markdown"]

    def test_empty_list(self):
        assert firecrawl_client.scrape_many([]) == []


class TestDiscoverPolicyUrls(unittest.TestCase):
    def setUp(self):
        firecrawl_client.reset_client()

    def tearDown(self):
        firecrawl_client.reset_client()

    def test_discovery_filters_and_includes_seed_url(self):
        mock_app = MagicMock()
        mock_app.map_url.return_value = {
            "links": [
                "https://example.com/blog/1",
                "https://example.com/terms",
                "https://example.com/privacy-policy",
                "https://example.com/about",
                "https://example.com/legal/dpa",
            ]
        }
        with patch.object(firecrawl_client, "_get_client", return_value=mock_app):
            results = firecrawl_client.discover_policy_urls(
                "https://example.com/", max_results=8
            )
            assert "https://example.com/terms" in results
            assert "https://example.com/privacy-policy" in results
            assert "https://example.com/legal/dpa" in results
            assert "https://example.com/blog/1" not in results
            assert "https://example.com/about" not in results


if __name__ == "__main__":
    unittest.main()
