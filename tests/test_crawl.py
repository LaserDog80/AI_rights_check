"""Tests for src.crawl — AI-assisted web crawling."""

import json
import unittest
from unittest.mock import MagicMock, patch

from src.crawl import _extract_links, ai_crawl


class TestExtractLinks(unittest.TestCase):
    def test_extracts_links(self):
        html = """
        <html><body>
            <a href="/terms">Terms</a>
            <a href="/privacy">Privacy</a>
            <a href="https://other.com/foo">External</a>
        </body></html>
        """
        links = _extract_links(html, "https://example.com")
        urls = [l["url"] for l in links]
        assert "https://example.com/terms" in urls
        assert "https://example.com/privacy" in urls
        # External link should be filtered out
        assert "https://other.com/foo" not in urls

    def test_skips_anchors_and_mailto(self):
        html = """
        <html><body>
            <a href="#section">Anchor</a>
            <a href="mailto:a@b.com">Email</a>
            <a href="/real-page">Real</a>
        </body></html>
        """
        links = _extract_links(html, "https://example.com")
        assert len(links) == 1
        assert links[0]["url"] == "https://example.com/real-page"

    def test_deduplicates(self):
        html = """
        <html><body>
            <a href="/terms">Terms</a>
            <a href="/terms">Terms again</a>
        </body></html>
        """
        links = _extract_links(html, "https://example.com")
        assert len(links) == 1


class TestAiCrawl(unittest.TestCase):
    @patch("src.crawl.fetch_terms_text")
    @patch("src.crawl._ask_llm_for_links")
    @patch("src.crawl.requests.get")
    def test_basic_crawl(self, mock_get, mock_ask_llm, mock_fetch):
        # Landing page
        mock_resp = MagicMock()
        mock_resp.text = '<html><body><a href="/terms">Terms</a></body></html>'
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        # LLM identifies one relevant link
        mock_ask_llm.return_value = [
            {"url": "https://example.com/terms", "likely_content": "Terms of Service", "priority": 10}
        ]

        # Text extraction
        mock_fetch.side_effect = [
            "Landing page text " * 20,
            "Terms and conditions full text " * 50,
        ]

        result = ai_crawl("https://example.com")
        assert result["page_count"] >= 1
        assert "combined_text" in result
        assert len(result["combined_text"]) > 0

    @patch("src.crawl._fetch_with_playwright", side_effect=Exception("browser failed"))
    @patch("src.crawl.requests.get")
    def test_crawl_failure(self, mock_get, mock_pw):
        import requests
        mock_get.side_effect = requests.RequestException("Network error")
        result = ai_crawl("https://example.com")
        assert result["page_count"] == 0
        assert "error" in result

    @patch("src.crawl.fetch_terms_text")
    @patch("src.crawl.requests.get")
    def test_crawl_no_links(self, mock_get, mock_fetch):
        mock_resp = MagicMock()
        mock_resp.text = '<html><body><p>No links here</p></body></html>'
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        mock_fetch.return_value = "Some text content from the page"

        result = ai_crawl("https://example.com")
        assert result["page_count"] == 1


if __name__ == "__main__":
    unittest.main()
