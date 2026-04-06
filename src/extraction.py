"""Text extraction from URLs, uploaded files, and raw text."""

import io
import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MAX_TEXT_LENGTH = 50_000

PASTE_OR_UPLOAD_HINT = (
    " Please copy and paste the Terms & Conditions text directly, or save the"
    " page as a file (PDF, HTML, DOCX) and upload it instead."
)

CLOUDFLARE_MSG = (
    "This site is protected by Cloudflare and cannot be fetched automatically."
    + PASTE_OR_UPLOAD_HINT
)

JS_RENDERED_MSG = (
    "This site requires JavaScript to display its content, so the text could"
    " not be extracted automatically." + PASTE_OR_UPLOAD_HINT
)


def _check_cloudflare(resp) -> None:
    """Raise ValueError if the response is a Cloudflare challenge page."""
    if resp.status_code == 403 and (
        "cf-mitigated" in resp.headers
        or "Just a moment" in resp.text[:1000]
    ):
        raise ValueError(CLOUDFLARE_MSG)


def _check_js_rendered(text: str) -> None:
    """Raise ValueError if the extracted text is too short, likely JS-rendered."""
    if len(text) < 100:
        raise ValueError(JS_RENDERED_MSG)


def _fetch_with_playwright(url: str) -> str:
    """Fetch a URL using a headless browser to bypass Cloudflare/JS rendering."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = ctx.new_page()
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(10000)
            html = page.content()
        finally:
            browser.close()

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:MAX_TEXT_LENGTH]


def fetch_terms_text(url: str) -> str:
    """Fetch a URL and extract the main text content.

    Tries trafilatura first, then requests + BeautifulSoup, then falls back
    to a headless browser (Playwright) for Cloudflare-protected or
    JS-rendered sites.
    """
    # --- Attempt 1: trafilatura (fast, handles many sites) ---
    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded, include_comments=False, include_tables=True
            )
            if text and len(text) > 200:
                return text[:MAX_TEXT_LENGTH]
    except Exception:
        pass

    # --- Attempt 2: requests + BeautifulSoup (fast fallback) ---
    needs_browser = False
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        _check_cloudflare(resp)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) >= 100:
            return text[:MAX_TEXT_LENGTH]
        needs_browser = True
    except ValueError:
        needs_browser = True

    # --- Attempt 3: headless browser (slow but handles Cloudflare/JS) ---
    if needs_browser:
        try:
            text = _fetch_with_playwright(url)
            if len(text) >= 100:
                return text
        except Exception:
            pass
        raise ValueError(
            "Could not extract text from this site, even with a headless browser."
            + PASTE_OR_UPLOAD_HINT
        )


def extract_text_from_file(file_storage) -> str:
    """Extract text from an uploaded file.

    Supports PDF, DOCX, TXT, HTML, RTF, and falls back to raw text decode.
    """
    filename = (file_storage.filename or "").lower()
    raw_bytes = file_storage.read()

    if filename.endswith(".pdf"):
        return _extract_pdf(raw_bytes)
    elif filename.endswith(".docx"):
        return _extract_docx(raw_bytes)
    elif filename.endswith(".html") or filename.endswith(".htm"):
        return _extract_html(raw_bytes)
    elif filename.endswith(".rtf"):
        return _extract_rtf(raw_bytes)
    else:
        # TXT and anything else — attempt raw text decode
        return _extract_plain(raw_bytes)


def _extract_pdf(raw_bytes: bytes) -> str:
    """Extract text from a PDF file using pdfplumber."""
    import pdfplumber

    pages_text = []
    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    combined = "\n\n".join(pages_text)
    return combined[:MAX_TEXT_LENGTH]


def _extract_docx(raw_bytes: bytes) -> str:
    """Extract text from a DOCX file using python-docx."""
    import docx

    doc = docx.Document(io.BytesIO(raw_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    combined = "\n\n".join(paragraphs)
    return combined[:MAX_TEXT_LENGTH]


def _extract_html(raw_bytes: bytes) -> str:
    """Extract text from an HTML file using BeautifulSoup."""
    text = raw_bytes.decode("utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    plain = soup.get_text(separator="\n", strip=True)
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    return plain[:MAX_TEXT_LENGTH]


def _extract_rtf(raw_bytes: bytes) -> str:
    """Extract text from an RTF file using striprtf."""
    from striprtf.striprtf import rtf_to_text

    rtf_content = raw_bytes.decode("utf-8", errors="replace")
    text = rtf_to_text(rtf_content)
    return text[:MAX_TEXT_LENGTH]


def _extract_plain(raw_bytes: bytes) -> str:
    """Decode raw bytes as plain text."""
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            text = raw_bytes.decode(encoding)
            return text[:MAX_TEXT_LENGTH]
        except (UnicodeDecodeError, ValueError):
            continue
    return raw_bytes.decode("utf-8", errors="replace")[:MAX_TEXT_LENGTH]
