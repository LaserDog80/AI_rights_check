"""Curated registry of popular image/video generation platforms.

Each entry captures the canonical legal-document URLs we want to analyse for a
given platform. The dropdown in the UI is built from this dict, and the
known-site analysis flow scrapes every URL listed here in parallel before
handing the combined text to the LLM.

Aggregator entries (Freepik, Krea, OpenArt, Weavy, fal.ai) include an
``underlying_models`` list and a ``stacked_terms_note`` so the analyser can
warn users that the aggregator's ToS layers on top of each model's own terms.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
CATEGORY_DIRECT = "direct"          # First-party image/video generators
CATEGORY_AGGREGATOR = "aggregator"  # Multi-model platforms
CATEGORY_AVATAR = "avatar"          # Avatar / character video generators


# ---------------------------------------------------------------------------
# Site registry
# ---------------------------------------------------------------------------
KNOWN_SITES: dict[str, dict] = {
    # ----- Direct image/video generators -----
    "midjourney": {
        "name": "Midjourney",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free Trial", "Basic", "Standard", "Pro", "Mega"],
        "urls": [
            "https://docs.midjourney.com/docs/terms-of-service",
            "https://docs.midjourney.com/docs/privacy-policy",
            "https://docs.midjourney.com/docs/community-guidelines",
        ],
    },
    "runway": {
        "name": "Runway (Gen-3 / Gen-4)",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free", "Standard", "Pro", "Unlimited", "Enterprise"],
        "urls": [
            "https://runwayml.com/terms-of-use",
            "https://runwayml.com/privacy-policy",
        ],
    },
    "pika": {
        "name": "Pika",
        "category": CATEGORY_DIRECT,
        "tiers": ["Basic", "Standard", "Pro", "Fancy"],
        "urls": [
            "https://pika.art/terms",
            "https://pika.art/privacy",
        ],
    },
    "luma": {
        "name": "Luma Dream Machine",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free", "Standard", "Pro", "Premier"],
        "urls": [
            "https://lumalabs.ai/legal/tos",
            "https://lumalabs.ai/legal/privacy-policy",
        ],
    },
    "sora": {
        "name": "Sora (OpenAI)",
        "category": CATEGORY_DIRECT,
        "tiers": ["Plus", "Pro"],
        "urls": [
            "https://openai.com/policies/terms-of-use",
            "https://openai.com/policies/sora-terms-of-use",
            "https://openai.com/policies/usage-policies",
            "https://openai.com/policies/privacy-policy",
        ],
    },
    "google_flow": {
        "name": "Google Flow (Veo 3 + Imagen)",
        "category": CATEGORY_DIRECT,
        "tiers": ["AI Pro", "AI Ultra"],
        "urls": [
            "https://policies.google.com/terms/generative-ai",
            "https://policies.google.com/terms/generative-ai/use-policy",
            "https://policies.google.com/privacy",
        ],
    },
    "kling": {
        "name": "Kling (Kuaishou)",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free", "Standard", "Pro", "Premier"],
        "urls": [
            "https://klingai.com/terms-of-service",
            "https://klingai.com/privacy-policy",
        ],
    },
    "minimax": {
        "name": "MiniMax / Hailuo",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free", "Standard", "Unlimited"],
        "urls": [
            "https://hailuoai.video/terms",
            "https://hailuoai.video/privacy",
        ],
    },
    "dreamina": {
        "name": "Dreamina (ByteDance / CapCut)",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free", "Pro"],
        "urls": [
            "https://dreamina.capcut.com/terms",
            "https://dreamina.capcut.com/privacy",
        ],
    },
    "grok": {
        "name": "Grok (xAI - Aurora)",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free", "Premium", "Premium+", "SuperGrok"],
        "urls": [
            "https://x.ai/legal/terms-of-service",
            "https://x.ai/legal/privacy-policy",
            "https://x.ai/legal/acceptable-use-policy",
        ],
    },
    "ideogram": {
        "name": "Ideogram",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free", "Basic", "Plus", "Pro"],
        "urls": [
            "https://about.ideogram.ai/legal/tos",
            "https://about.ideogram.ai/legal/privacy",
        ],
    },
    "leonardo": {
        "name": "Leonardo.Ai",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free", "Apprentice", "Artisan", "Maestro"],
        "urls": [
            "https://leonardo.ai/terms-of-service/",
            "https://leonardo.ai/privacy-policy/",
        ],
    },
    "firefly": {
        "name": "Adobe Firefly",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free", "Standard", "Pro", "Premium"],
        "urls": [
            "https://www.adobe.com/legal/terms.html",
            "https://www.adobe.com/legal/licenses-terms/adobe-gen-ai-user-guidelines.html",
            "https://helpx.adobe.com/firefly/using/firefly-faq.html",
        ],
        "highlights": [
            "Adobe is one of the only providers offering IP indemnity for "
            "commercial outputs (enterprise tiers).",
        ],
    },
    "recraft": {
        "name": "Recraft",
        "category": CATEGORY_DIRECT,
        "tiers": ["Free", "Basic", "Advanced", "Pro"],
        "urls": [
            "https://www.recraft.ai/terms",
            "https://www.recraft.ai/privacy",
        ],
    },
    "flux": {
        "name": "Flux (Black Forest Labs)",
        "category": CATEGORY_DIRECT,
        "tiers": ["API"],
        "urls": [
            "https://blackforestlabs.ai/terms-of-service/",
            "https://blackforestlabs.ai/privacy-policy/",
        ],
    },

    # ----- Aggregators -----
    "freepik": {
        "name": "Freepik",
        "category": CATEGORY_AGGREGATOR,
        "tiers": ["Free", "Premium", "Premium+", "Enterprise"],
        "urls": [
            "https://www.freepik.com/terms_of_use_premium",
            "https://www.freepik.com/legal/terms-of-use",
            "https://www.freepik.com/legal/privacy-policy",
            "https://www.freepik.com/legal/cookies-policy",
        ],
        "underlying_models": ["Flux", "Kling", "Mystic", "Google Imagen", "Magnific"],
        "stacked_terms_note": (
            "Freepik aggregates third-party models. When you generate with "
            "Kling/Flux/Imagen via Freepik, BOTH Freepik's terms AND the "
            "underlying model's terms typically apply. The stricter wins."
        ),
    },
    "krea": {
        "name": "Krea",
        "category": CATEGORY_AGGREGATOR,
        "tiers": ["Free", "Basic", "Pro", "Max"],
        "urls": [
            "https://www.krea.ai/terms",
            "https://www.krea.ai/privacy",
        ],
        "underlying_models": ["Flux", "Stable Diffusion", "Kling", "Hailuo", "Veo"],
        "stacked_terms_note": (
            "Krea hosts third-party models. Both Krea's terms and the "
            "underlying model's terms may apply to outputs."
        ),
    },
    "openart": {
        "name": "OpenArt",
        "category": CATEGORY_AGGREGATOR,
        "tiers": ["Free", "Hobbyist", "Pro", "Premium"],
        "urls": [
            "https://openart.ai/terms",
            "https://openart.ai/privacy",
        ],
        "underlying_models": ["Stable Diffusion", "Flux", "Kling", "DALL-E"],
        "stacked_terms_note": (
            "OpenArt aggregates multiple image and video models — terms stack."
        ),
    },
    "weavy": {
        "name": "Weavy",
        "category": CATEGORY_AGGREGATOR,
        "tiers": ["Free", "Pro", "Team"],
        "urls": [
            "https://www.weavy.ai/terms",
            "https://www.weavy.ai/privacy",
        ],
        "underlying_models": ["Flux", "Kling", "Runway", "Luma", "Stable Diffusion"],
        "stacked_terms_note": (
            "Weavy is a node-based creative canvas hosting many models — "
            "outputs are subject to Weavy's terms plus each underlying provider."
        ),
    },
    "fal": {
        "name": "fal.ai",
        "category": CATEGORY_AGGREGATOR,
        "tiers": ["Free", "Pay-as-you-go", "Growth", "Enterprise"],
        "urls": [
            "https://fal.ai/terms-of-service",
            "https://fal.ai/privacy-policy",
        ],
        "underlying_models": [
            "Flux", "Kling", "Hailuo", "Stable Diffusion", "LTX", "Hunyuan",
        ],
        "stacked_terms_note": (
            "fal.ai is a model-hosting API platform — fal.ai's terms apply, "
            "plus each underlying model provider's licence."
        ),
    },

    # ----- Avatar / character video -----
    "hedra": {
        "name": "Hedra",
        "category": CATEGORY_AVATAR,
        "tiers": ["Free", "Basic", "Creator", "Pro"],
        "urls": [
            "https://www.hedra.com/terms-of-service",
            "https://www.hedra.com/privacy-policy",
        ],
    },
    "heygen": {
        "name": "HeyGen",
        "category": CATEGORY_AVATAR,
        "tiers": ["Free", "Creator", "Team", "Enterprise"],
        "urls": [
            "https://www.heygen.com/policy/terms-of-service",
            "https://www.heygen.com/policy/privacy-policy",
            "https://www.heygen.com/policy/moderation-policy",
        ],
    },
    "synthesia": {
        "name": "Synthesia",
        "category": CATEGORY_AVATAR,
        "tiers": ["Starter", "Creator", "Enterprise"],
        "urls": [
            "https://www.synthesia.io/terms",
            "https://www.synthesia.io/privacy-notice",
            "https://www.synthesia.io/acceptable-use-policy",
        ],
    },
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def get_site(slug: str) -> dict | None:
    """Look up a site by slug. Returns ``None`` if unknown."""
    return KNOWN_SITES.get(slug)


def list_sites() -> list[dict]:
    """Return a UI-friendly, alphabetised list of all known sites grouped by category."""
    items = []
    for slug, entry in KNOWN_SITES.items():
        items.append({
            "slug": slug,
            "name": entry["name"],
            "category": entry.get("category", CATEGORY_DIRECT),
            "tiers": entry.get("tiers", []),
            "is_aggregator": entry.get("category") == CATEGORY_AGGREGATOR,
        })
    # Sort by category then name for a stable dropdown ordering
    category_order = {CATEGORY_DIRECT: 0, CATEGORY_AGGREGATOR: 1, CATEGORY_AVATAR: 2}
    items.sort(key=lambda x: (category_order.get(x["category"], 99), x["name"].lower()))
    return items
