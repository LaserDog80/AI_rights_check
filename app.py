"""AI Terms & Conditions Analyzer - Flask Application."""

import json
import os
import re

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Nebius / OpenAI-compatible client
# ---------------------------------------------------------------------------
client = OpenAI(
    api_key=os.getenv("NEBIUS_API_KEY", ""),
    base_url=os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1"),
)
MODEL = os.getenv("NEBIUS_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct")

# ---------------------------------------------------------------------------
# T&C text extraction
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_terms_text(url: str) -> str:
    """Fetch a URL and extract the main text content."""
    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False,
                                       include_tables=True)
            if text and len(text) > 200:
                return text[:15000]
    except Exception:
        pass

    # Fallback: requests + BeautifulSoup
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:15000]


# ---------------------------------------------------------------------------
# AI analysis
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are an expert AI-policy analyst. The user will give you the Terms & Conditions \
(or Terms of Service / Acceptable Use Policy) text from a generative-AI platform.

Analyse the text and return a JSON object with EXACTLY this schema (no markdown, \
no code fences, pure JSON):

{
  "platform_name": "<detected platform name>",
  "classification": "<one of: Restrictive | Moderate | Permissive | Unclear>",
  "overall_verdict": "<1-2 sentence plain-english verdict>",
  "risk_score": <integer 1-10, 10 = highest risk to users>,
  "categories": {
    "training_on_user_content": {
      "status": "<Yes | No | Opt-out | Unclear>",
      "detail": "<short explanation>"
    },
    "ownership_of_outputs": {
      "status": "<User | Platform | Shared | Unclear>",
      "detail": "<short explanation>"
    },
    "enterprise_exclusions": {
      "status": "<Yes | No | Partial | Unclear>",
      "detail": "<short explanation>"
    },
    "data_retention": {
      "status": "<Retained | Deleted | Configurable | Unclear>",
      "detail": "<short explanation>"
    },
    "third_party_sharing": {
      "status": "<Yes | No | Anonymised | Unclear>",
      "detail": "<short explanation>"
    },
    "content_restrictions": {
      "status": "<Strict | Moderate | Minimal | Unclear>",
      "detail": "<short explanation>"
    },
    "liability_limitation": {
      "status": "<Strong | Moderate | Weak | Unclear>",
      "detail": "<short explanation>"
    },
    "ip_indemnification": {
      "status": "<Yes | No | Partial | Unclear>",
      "detail": "<short explanation>"
    }
  },
  "checklist": [
    {"item": "<short checklist item>", "pass": <true|false|null>}
  ],
  "key_quotes": ["<relevant verbatim quote from T&Cs>", "..."],
  "recommendations": ["<actionable recommendation>", "..."]
}

Rules:
- checklist should have 6-10 items covering the most important rights & risks.
- pass=true means favourable for the user, false means unfavourable, null means unclear.
- key_quotes: pick 2-4 of the most impactful verbatim sentences.
- recommendations: 2-4 practical next-steps for the user.
- If the text doesn't look like T&Cs, set classification to "Unclear" and explain in overall_verdict.
"""


def analyse_terms(terms_text: str) -> dict:
    """Send terms text to the LLM and return structured analysis."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": terms_text},
        ],
        temperature=0.2,
        max_tokens=3000,
    )
    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyse", methods=["POST"])
def api_analyse():
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    raw_text = data.get("raw_text", "").strip()

    if not url and not raw_text:
        return jsonify({"error": "Provide a URL or paste the T&C text."}), 400

    try:
        if url:
            terms_text = fetch_terms_text(url)
        else:
            terms_text = raw_text[:15000]

        if len(terms_text) < 100:
            return jsonify({"error": "Could not extract enough text. Try pasting the T&Cs directly."}), 400

        result = analyse_terms(terms_text)
        result["source_url"] = url or "pasted text"
        result["text_length"] = len(terms_text)
        return jsonify(result)

    except json.JSONDecodeError:
        return jsonify({"error": "AI returned invalid JSON. Please try again."}), 502
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
