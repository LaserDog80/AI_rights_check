"""LLM-powered analysis of Terms & Conditions text."""

import json
import os
import re

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# OpenAI-compatible client
# ---------------------------------------------------------------------------
_default_client = None
_default_model = None


def _get_default_client():
    global _default_client, _default_model
    if _default_client is None:
        _default_client = OpenAI(
            api_key=os.getenv("NEBIUS_API_KEY", ""),
            base_url=os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1"),
        )
        _default_model = os.getenv(
            "NEBIUS_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct"
        )
    return _default_client, _default_model


def get_client(api_key: str = "", base_url: str = "", model: str = ""):
    """Return an OpenAI client + model, using user-provided or default config."""
    if api_key:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url or "https://api.studio.nebius.com/v1",
        )
        m = model or "meta-llama/Meta-Llama-3.1-70B-Instruct"
        return client, m
    return _get_default_client()


def _parse_llm_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON from LLM output."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Quick analysis
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


def analyse_terms(terms_text: str, api_key: str = "", base_url: str = "",
                  model: str = "") -> dict:
    """Send terms text to the LLM and return structured analysis."""
    client, m = get_client(api_key, base_url, model)
    response = client.chat.completions.create(
        model=m,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": terms_text},
        ],
        temperature=0.2,
        max_tokens=3000,
    )
    return _parse_llm_json(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# Deep analysis
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


def deep_analyse_terms(terms_text: str, tier: str = "", api_key: str = "",
                       base_url: str = "", model: str = "") -> dict:
    """Send terms text to the LLM for deep clause-by-clause analysis."""
    system_prompt = DEEP_SYSTEM_PROMPT
    if tier:
        system_prompt += TIER_PROMPT_ADDENDUM.format(tier=tier)

    client, m = get_client(api_key, base_url, model)
    response = client.chat.completions.create(
        model=m,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": terms_text},
        ],
        temperature=0.2,
        max_tokens=8000,
    )
    return _parse_llm_json(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# Tier comparison
# ---------------------------------------------------------------------------
TIER_COMPARISON_PROMPT = """\
You are a senior AI-policy lawyer specialising in commercial licensing and indemnity. \
The user will give you the Terms & Conditions (or Terms of Service / Acceptable Use \
Policy / Pricing page) text from a generative-AI platform.

Your task is to identify ALL pricing tiers mentioned in the text and compare them \
side-by-side. Focus especially on indemnity, provenance, and commercial protection.

Return a JSON object with EXACTLY this schema (no markdown, no code fences, pure JSON):

{
  "platform_name": "<detected platform name>",
  "tiers_detected": ["<tier name>", ...],
  "tier_matrix": [
    {
      "tier_name": "<tier name>",
      "indemnity": {
        "covered": <true|false|null>,
        "detail": "<what indemnity protection is offered, if any>"
      },
      "provenance": {
        "covered": <true|false|null>,
        "detail": "<audit trails, content provenance, watermarking, etc.>"
      },
      "output_ownership": {
        "covered": <true|false|null>,
        "detail": "<who owns the generated output>"
      },
      "commercial_use": {
        "covered": <true|false|null>,
        "detail": "<can outputs be used commercially>"
      },
      "training_opt_out": {
        "covered": <true|false|null>,
        "detail": "<can user opt out of their data being used for training>"
      },
      "license_to_provider": {
        "scope": "<None | Limited | Broad | Unclear>",
        "detail": "<what licence the user grants the provider>"
      },
      "data_retention": {
        "policy": "<Deleted | Retained | Configurable | Unclear>",
        "detail": "<retention and deletion rights>"
      },
      "third_party_sharing": {
        "shared": <true|false|null>,
        "detail": "<is user data shared with third parties>"
      }
    }
  ],
  "comparison_summary": "<2-4 sentence summary of the key differences across tiers>",
  "indemnity_deep_dive": {
    "overview": "<detailed explanation of indemnity provisions>",
    "which_tiers_covered": ["<tier names with indemnity>"],
    "exclusions": ["<what is NOT covered even with indemnity>"],
    "caps": "<any monetary caps on indemnity>"
  },
  "provenance_deep_dive": {
    "overview": "<detailed explanation of provenance/audit features>",
    "which_tiers_covered": ["<tier names with provenance features>"],
    "capabilities": ["<specific provenance features available>"]
  },
  "upgrade_recommendation": "<which tier offers the best protection-to-cost ratio and why>",
  "risk_assessment": {
    "lowest_risk_tier": "<tier name>",
    "highest_risk_tier": "<tier name>",
    "explanation": "<why>"
  }
}

Rules:
- If the text only mentions one tier or no tier distinctions, still return the matrix \
  with whatever information is available. Set tiers_detected to the single tier found.
- covered=true means the feature is available on that tier, false means not, null means unclear.
- Be precise with what each tier actually offers — don't guess. Mark unclear if the text is ambiguous.
- The indemnity_deep_dive and provenance_deep_dive sections should be thorough.
- If the text doesn't look like T&Cs, set platform_name to "Unknown" and explain in comparison_summary.
"""


def tier_compare_terms(terms_text: str, api_key: str = "", base_url: str = "",
                       model: str = "") -> dict:
    """Analyse terms text and produce a cross-tier comparison matrix."""
    client, m = get_client(api_key, base_url, model)
    response = client.chat.completions.create(
        model=m,
        messages=[
            {"role": "system", "content": TIER_COMPARISON_PROMPT},
            {"role": "user", "content": terms_text},
        ],
        temperature=0.2,
        max_tokens=8000,
    )
    return _parse_llm_json(response.choices[0].message.content)
