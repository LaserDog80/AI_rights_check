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
# Deep analysis via Claude
# ---------------------------------------------------------------------------
DEEP_SYSTEM_PROMPT = """\
You are a senior AI-policy lawyer and technical analyst. The user will give you \
the Terms & Conditions (or Terms of Service / Acceptable Use Policy) text from a \
generative-AI platform.

Perform a deep, clause-by-clause analysis. Return a JSON object with EXACTLY this \
schema (no markdown, no code fences, pure JSON):

{
  "platform_name": "<detected platform name>",
  "document_type": "<Terms of Service | Privacy Policy | Acceptable Use Policy | Combined | Other>",
  "analysis_depth": "deep",
  "executive_summary": "<3-5 sentence executive summary written for a non-lawyer>",
  "risk_score": <integer 1-10, 10 = highest risk to users>,
  "classification": "<Restrictive | Moderate | Permissive | Unclear>",
  "clauses": [
    {
      "clause_title": "<descriptive short title for this clause>",
      "original_text": "<verbatim excerpt from the T&Cs (key sentence or paragraph)>",
      "plain_english": "<what this actually means in everyday language>",
      "risk_level": "<Critical | High | Medium | Low | Informational>",
      "category": "<one of: Data Rights | IP Ownership | Training & Model Use | Privacy | Liability | Content Policy | Termination | Indemnification | Dispute Resolution | Compliance | Other>",
      "flags": ["<short flag description, e.g. 'Broad data licence', 'Unilateral change rights'>"]
    }
  ],
  "hidden_concerns": [
    {
      "title": "<short title>",
      "description": "<explanation of the buried or easily-missed provision>",
      "severity": "<Critical | High | Medium | Low>"
    }
  ],
  "comparison_to_industry": {
    "better_than_average": ["<areas where this platform is more user-friendly than typical>"],
    "worse_than_average": ["<areas where this platform is more restrictive than typical>"],
    "standard": ["<areas that are roughly industry-standard>"]
  },
  "user_rights_summary": {
    "what_you_keep": ["<rights the user retains>"],
    "what_you_give_up": ["<rights the user surrenders or licenses away>"],
    "what_is_unclear": ["<rights that are ambiguous in the text>"]
  },
  "actionable_recommendations": [
    {
      "priority": "<Critical | High | Medium | Low>",
      "action": "<specific actionable recommendation>"
    }
  ],
  "legal_red_flags": ["<brief description of any legally aggressive or unusual clauses>"]
}

Rules:
- Analyse EVERY significant clause, not just the obvious ones. Aim for 8-20 clauses.
- hidden_concerns should surface provisions that are easily overlooked but materially \
  affect users (buried in dense paragraphs, vague language, unilateral change rights, etc.).
- comparison_to_industry should compare against norms from OpenAI, Google, Microsoft, \
  Anthropic, Meta, and Stability AI terms as of 2025.
- Be precise with verbatim quotes — copy exact wording from the text.
- If the text doesn't look like T&Cs, return minimal results with classification "Unclear".
"""


TIER_PROMPT_ADDENDUM = """

IMPORTANT — Tier-specific analysis:
The user has indicated they are on the "{tier}" tier/plan. You MUST:
1. Identify any clauses that differ between pricing tiers (free, standard, pro, \
   enterprise, team, etc.).
2. Highlight tier-specific privileges or restrictions for the "{tier}" tier — such as \
   data training opt-outs, enhanced IP indemnification, different retention policies, \
   or SLA guarantees that only apply to certain tiers.
3. In each clause analysis, note if the clause applies universally or only to specific tiers.
4. Add a top-level key "tier_analysis" to the JSON output:
   "tier_analysis": {{
     "selected_tier": "{tier}",
     "tier_specific_benefits": ["<benefits unique to this tier>"],
     "tier_specific_restrictions": ["<restrictions unique to this tier>"],
     "upgrade_considerations": ["<what changes if the user upgrades/downgrades>"]
   }}
"""


def deep_analyse_terms(terms_text: str, tier: str = "") -> dict:
    """Send terms text to the LLM for deep clause-by-clause analysis.

    Uses the Nebius (OpenAI-compatible) endpoint for the deep analysis.
    Optionally includes tier-specific analysis instructions.
    """
    system_prompt = DEEP_SYSTEM_PROMPT
    if tier:
        system_prompt += TIER_PROMPT_ADDENDUM.format(tier=tier)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": terms_text},
        ],
        temperature=0.2,
        max_tokens=8000,
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


@app.route("/api/deep-analyse", methods=["POST"])
def api_deep_analyse():
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    raw_text = data.get("raw_text", "").strip()
    tier = data.get("tier", "").strip()

    if not url and not raw_text:
        return jsonify({"error": "Provide a URL or paste the T&C text."}), 400

    try:
        if url:
            terms_text = fetch_terms_text(url)
        else:
            terms_text = raw_text[:15000]

        if len(terms_text) < 100:
            return jsonify({"error": "Could not extract enough text. Try pasting the T&Cs directly."}), 400

        result = deep_analyse_terms(terms_text, tier=tier)
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
