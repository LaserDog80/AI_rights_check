# AI Terms Analyzer ⚡

A web application that interrogates the Terms & Conditions of generative AI platforms and produces a structured verdict report.

## What it does

Paste a URL to any GenAI platform's Terms of Service (or paste the text directly) and the analyzer will:

- **Fetch & extract** the T&C text from the page
- **Cross-check** against key categories:
  - Training on user content
  - Ownership of outputs
  - Enterprise exclusions
  - Data retention policy
  - Third-party sharing
  - Content restrictions
  - Liability limitation
  - IP indemnification
- **Classify** the platform as Restrictive / Moderate / Permissive / Unclear
- **Output** a risk score, detailed verdict, quick checklist, key quotes, and recommendations

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file (see `.env.example`):

```
NEBIUS_API_KEY=your-nebius-token-factory-key
NEBIUS_BASE_URL=https://api.studio.nebius.com/v1
NEBIUS_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct
```

## Run

```bash
python app.py
```

Then open http://localhost:5000 in your browser.

## Tests

```bash
python -m pytest tests/ -v
```

## Tech Stack

- **Backend**: Flask + OpenAI-compatible client (Nebius AI)
- **Frontend**: Single-page HTML/CSS/JS with dark theme
- **Extraction**: Trafilatura + BeautifulSoup fallback
