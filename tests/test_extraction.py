"""Tests for src.extraction — file and URL text extraction."""

import io
import unittest
from unittest.mock import MagicMock, patch

from src.extraction import (
    extract_text_from_file,
    _extract_html,
    _extract_plain,
    MAX_TEXT_LENGTH,
)


class TestExtractPlain(unittest.TestCase):
    def test_utf8_text(self):
        raw = b"Hello, this is a plain text T&C document."
        result = _extract_plain(raw)
        assert result == "Hello, this is a plain text T&C document."

    def test_latin1_fallback(self):
        raw = "Caf\xe9 terms and conditions".encode("latin-1")
        result = _extract_plain(raw)
        assert "Caf" in result

    def test_truncation(self):
        raw = ("x" * (MAX_TEXT_LENGTH + 1000)).encode("utf-8")
        result = _extract_plain(raw)
        assert len(result) == MAX_TEXT_LENGTH


class TestExtractHtml(unittest.TestCase):
    def test_strips_script_and_style(self):
        html = b"<html><head><style>body{}</style></head><body><script>alert(1)</script><p>Terms here</p></body></html>"
        result = _extract_html(html)
        assert "Terms here" in result
        assert "alert" not in result
        assert "body{}" not in result

    def test_strips_nav_footer(self):
        html = b"<html><body><nav>Menu</nav><main><p>Real content</p></main><footer>Footer</footer></body></html>"
        result = _extract_html(html)
        assert "Real content" in result
        assert "Menu" not in result
        assert "Footer" not in result


class TestExtractTextFromFile(unittest.TestCase):
    def test_txt_file(self):
        mock_file = MagicMock()
        mock_file.filename = "terms.txt"
        mock_file.read.return_value = b"These are the terms and conditions for our service."
        result = extract_text_from_file(mock_file)
        assert "terms and conditions" in result

    def test_html_file(self):
        mock_file = MagicMock()
        mock_file.filename = "terms.html"
        mock_file.read.return_value = b"<html><body><p>Terms of Service</p></body></html>"
        result = extract_text_from_file(mock_file)
        assert "Terms of Service" in result

    @patch("pdfplumber.open")
    def test_pdf_file(self, mock_open):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "PDF terms content here"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_pdf

        mock_file = MagicMock()
        mock_file.filename = "terms.pdf"
        mock_file.read.return_value = b"fake pdf bytes"
        result = extract_text_from_file(mock_file)
        assert "PDF terms content" in result

    @patch("docx.Document")
    def test_docx_file(self, mock_document):
        mock_para = MagicMock()
        mock_para.text = "DOCX terms content"
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_document.return_value = mock_doc

        mock_file = MagicMock()
        mock_file.filename = "terms.docx"
        mock_file.read.return_value = b"fake docx bytes"
        result = extract_text_from_file(mock_file)
        assert "DOCX terms content" in result

    def test_unknown_format_treated_as_text(self):
        mock_file = MagicMock()
        mock_file.filename = "terms.xyz"
        mock_file.read.return_value = b"Some unknown format but still text"
        result = extract_text_from_file(mock_file)
        assert "unknown format" in result


class TestExtractRtf(unittest.TestCase):
    @patch("src.extraction.rtf_to_text", create=True)
    def test_rtf_file(self, mock_rtf_to_text):
        # We need to patch at the right level
        from unittest.mock import patch as p
        with p("striprtf.striprtf.rtf_to_text", return_value="RTF terms content"):
            mock_file = MagicMock()
            mock_file.filename = "terms.rtf"
            mock_file.read.return_value = b"{\\rtf1 RTF terms content}"
            result = extract_text_from_file(mock_file)
            assert result  # Just verify it returns something without error


if __name__ == "__main__":
    unittest.main()
