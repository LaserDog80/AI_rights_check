"""Tests for the AI Terms Analyzer app."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.routes import app as flask_app
import src.analysis as analysis_module
import src.extraction as extraction_module


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"AI Terms Analyzer" in resp.data


def test_analyse_missing_input(client):
    resp = client.post("/api/analyse", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_analyse_short_text(client):
    resp = client.post("/api/analyse", json={"raw_text": "short"})
    assert resp.status_code == 400


MOCK_AI_RESPONSE = json.dumps({
    "platform_name": "TestAI",
    "classification": "Moderate",
    "overall_verdict": "This platform uses your data for training but offers opt-out.",
    "risk_score": 5,
    "categories": {
        "training_on_user_content": {"status": "Opt-out", "detail": "Users can opt out."},
        "ownership_of_outputs": {"status": "User", "detail": "Users own outputs."},
        "enterprise_exclusions": {"status": "Yes", "detail": "Enterprise plans excluded."},
        "data_retention": {"status": "Configurable", "detail": "Users can delete."},
        "third_party_sharing": {"status": "Anonymised", "detail": "Only anonymised data shared."},
        "content_restrictions": {"status": "Moderate", "detail": "Standard restrictions."},
        "liability_limitation": {"status": "Strong", "detail": "Broad limitation clause."},
        "ip_indemnification": {"status": "Partial", "detail": "Only for paid tiers."},
    },
    "checklist": [
        {"item": "Data not used for training by default", "pass": False},
        {"item": "User owns output", "pass": True},
    ],
    "key_quotes": ["We may use your content to improve our services."],
    "recommendations": ["Enable the opt-out toggle in settings."],
})


@patch("src.analysis._get_default_client")
def test_analyse_with_raw_text(mock_get_client, client):
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_AI_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_resp
    mock_get_client.return_value = (mock_openai, "test-model")

    long_text = "Terms and Conditions: " + "a " * 200
    resp = client.post("/api/analyse", json={"raw_text": long_text})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["platform_name"] == "TestAI"
    assert data["classification"] == "Moderate"
    assert len(data["checklist"]) == 2


@patch("src.routes.fetch_terms_text", return_value="Terms " * 100)
@patch("src.analysis._get_default_client")
def test_analyse_with_url(mock_get_client, mock_fetch, client):
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_AI_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_resp
    mock_get_client.return_value = (mock_openai, "test-model")

    resp = client.post("/api/analyse", json={"url": "https://example.com/terms"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["source_url"] == "https://example.com/terms"


# ---------------------------------------------------------------------------
# Deep analysis endpoint tests
# ---------------------------------------------------------------------------
MOCK_DEEP_RESPONSE = json.dumps({
    "platform_name": "TestAI",
    "document_type": "Terms of Service",
    "analysis_depth": "deep",
    "executive_summary": "This platform retains broad rights over user data.",
    "risk_score": 7,
    "classification": "Restrictive",
    "clauses": [
        {
            "clause_title": "Data Licence Grant",
            "original_text": "You grant us a worldwide licence to use your content.",
            "plain_english": "They can use anything you upload however they want.",
            "risk_level": "High",
            "category": "Data Rights",
            "flags": ["Broad data licence"],
        }
    ],
    "hidden_concerns": [
        {
            "title": "Unilateral change rights",
            "description": "The platform can change terms at any time without notice.",
            "severity": "Critical",
        }
    ],
    "comparison_to_industry": {
        "better_than_average": ["Transparent data deletion process"],
        "worse_than_average": ["Broad training data rights"],
        "standard": ["Standard liability limitations"],
    },
    "user_rights_summary": {
        "what_you_keep": ["Output ownership"],
        "what_you_give_up": ["Training opt-out"],
        "what_is_unclear": ["Data retention timeline"],
    },
    "actionable_recommendations": [
        {"priority": "High", "action": "Negotiate a DPA before uploading sensitive data."}
    ],
    "legal_red_flags": ["Broad IP licence survives termination"],
})


def test_deep_analyse_missing_input(client):
    resp = client.post("/api/deep-analyse", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_deep_analyse_short_text(client):
    resp = client.post("/api/deep-analyse", json={"raw_text": "short"})
    assert resp.status_code == 400


@patch("src.analysis._get_default_client")
def test_deep_analyse_with_raw_text(mock_get_client, client):
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_DEEP_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_resp
    mock_get_client.return_value = (mock_openai, "test-model")

    long_text = "Terms and Conditions: " + "a " * 200
    resp = client.post("/api/deep-analyse", json={"raw_text": long_text})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["platform_name"] == "TestAI"
    assert data["analysis_depth"] == "deep"
    assert data["classification"] == "Restrictive"
    assert len(data["clauses"]) == 1
    assert data["clauses"][0]["risk_level"] == "High"
    assert len(data["hidden_concerns"]) == 1
    assert len(data["legal_red_flags"]) == 1


@patch("src.routes.fetch_terms_text", return_value="Terms " * 100)
@patch("src.analysis._get_default_client")
def test_deep_analyse_with_url(mock_get_client, mock_fetch, client):
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_DEEP_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_resp
    mock_get_client.return_value = (mock_openai, "test-model")

    resp = client.post("/api/deep-analyse", json={"url": "https://example.com/terms"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["source_url"] == "https://example.com/terms"
    assert data["analysis_depth"] == "deep"


MOCK_DEEP_TIER_RESPONSE = json.dumps({
    **json.loads(MOCK_DEEP_RESPONSE),
    "tier_analysis": {
        "selected_tier": "Pro",
        "tier_specific_benefits": ["Training opt-out enabled by default"],
        "tier_specific_restrictions": ["Higher rate limits but same data policy"],
        "upgrade_considerations": ["Enterprise tier adds IP indemnification"],
    },
})


@patch("src.analysis._get_default_client")
def test_deep_analyse_with_tier(mock_get_client, client):
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_DEEP_TIER_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_resp
    mock_get_client.return_value = (mock_openai, "test-model")

    long_text = "Terms and Conditions: " + "a " * 200
    resp = client.post("/api/deep-analyse", json={"raw_text": long_text, "tier": "Pro"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["tier_analysis"]["selected_tier"] == "Pro"
    assert len(data["tier_analysis"]["tier_specific_benefits"]) == 1


# ---------------------------------------------------------------------------
# Tier comparison endpoint tests
# ---------------------------------------------------------------------------
MOCK_TIER_COMPARE_RESPONSE = json.dumps({
    "platform_name": "TestAI",
    "tiers_detected": ["Free", "Pro", "Enterprise"],
    "tier_matrix": [
        {
            "tier_name": "Free",
            "indemnity": {"covered": False, "detail": "No indemnity on free tier"},
            "provenance": {"covered": False, "detail": "No provenance features"},
            "output_ownership": {"covered": True, "detail": "User owns outputs"},
            "commercial_use": {"covered": True, "detail": "Commercial use allowed"},
            "training_opt_out": {"covered": False, "detail": "Cannot opt out"},
            "license_to_provider": {"scope": "Broad", "detail": "Broad licence granted"},
            "data_retention": {"policy": "Retained", "detail": "Data retained indefinitely"},
            "third_party_sharing": {"shared": True, "detail": "Shared with partners"},
        },
        {
            "tier_name": "Enterprise",
            "indemnity": {"covered": True, "detail": "Full IP indemnification"},
            "provenance": {"covered": True, "detail": "Audit trails available"},
            "output_ownership": {"covered": True, "detail": "User owns outputs"},
            "commercial_use": {"covered": True, "detail": "Full commercial rights"},
            "training_opt_out": {"covered": True, "detail": "Opted out by default"},
            "license_to_provider": {"scope": "Limited", "detail": "Minimal licence"},
            "data_retention": {"policy": "Configurable", "detail": "Custom retention"},
            "third_party_sharing": {"shared": False, "detail": "No sharing"},
        },
    ],
    "comparison_summary": "Enterprise tier offers significantly better protection.",
    "indemnity_deep_dive": {
        "overview": "Only Enterprise tier provides indemnity.",
        "which_tiers_covered": ["Enterprise"],
        "exclusions": ["Wilful infringement"],
        "caps": "$1M aggregate",
    },
    "provenance_deep_dive": {
        "overview": "Audit features only on Enterprise.",
        "which_tiers_covered": ["Enterprise"],
        "capabilities": ["Content watermarking", "Audit log access"],
    },
    "upgrade_recommendation": "Enterprise offers the best protection for commercial use.",
    "risk_assessment": {
        "lowest_risk_tier": "Enterprise",
        "highest_risk_tier": "Free",
        "explanation": "Free tier lacks indemnity and training opt-out.",
    },
})


@patch("src.analysis._get_default_client")
def test_tier_compare_with_raw_text(mock_get_client, client):
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_TIER_COMPARE_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_resp
    mock_get_client.return_value = (mock_openai, "test-model")

    long_text = "Terms and Conditions: " + "a " * 200
    resp = client.post("/api/tier-compare", json={"raw_text": long_text})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["platform_name"] == "TestAI"
    assert len(data["tiers_detected"]) == 3
    assert len(data["tier_matrix"]) == 2
    assert data["indemnity_deep_dive"]["which_tiers_covered"] == ["Enterprise"]


def test_tier_compare_missing_input(client):
    resp = client.post("/api/tier-compare", json={})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# File upload endpoint tests
# ---------------------------------------------------------------------------
@patch("src.analysis._get_default_client")
def test_upload_txt_file(mock_get_client, client):
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_AI_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_resp
    mock_get_client.return_value = (mock_openai, "test-model")

    import io
    txt_content = ("Terms and Conditions for TestAI service. " * 20).encode("utf-8")
    data = {"file": (io.BytesIO(txt_content), "terms.txt"), "mode": "quick"}
    resp = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    result = resp.get_json()
    assert result["platform_name"] == "TestAI"
    assert "uploaded:" in result["source_url"]


def test_upload_no_file(client):
    resp = client.post("/api/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Known-sites endpoint
# ---------------------------------------------------------------------------
def test_known_sites_endpoint(client):
    resp = client.get("/api/known-sites")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "sites" in data
    assert "firecrawl_enabled" in data
    slugs = [s["slug"] for s in data["sites"]]
    # Spot-check a few of the user-requested platforms
    for slug in ["midjourney", "runway", "freepik", "fal", "heygen"]:
        assert slug in slugs


@patch("src.crawl.firecrawl_client.is_enabled", return_value=False)
@patch("src.crawl.fetch_terms_text", return_value="Curated terms text " * 200)
@patch("src.analysis._get_default_client")
def test_analyse_with_known_site(mock_get_client, mock_fetch, mock_fc_enabled, client):
    """Picking a known-site slug routes through known_site_crawl."""
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_AI_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_resp
    mock_get_client.return_value = (mock_openai, "test-model")

    resp = client.post("/api/analyse", json={"known_site": "midjourney"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["source_url"] == "Midjourney"
    assert "known_site" in data
    assert data["known_site"]["name"] == "Midjourney"
    assert data["known_site"]["is_aggregator"] is False


@patch("src.crawl.firecrawl_client.is_enabled", return_value=False)
@patch("src.crawl.fetch_terms_text", return_value="Aggregator policy text " * 200)
@patch("src.analysis._get_default_client")
def test_analyse_with_aggregator_known_site(mock_get_client, mock_fetch, mock_fc_enabled, client):
    """Aggregators surface stacked-terms metadata in the response."""
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_AI_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_resp
    mock_get_client.return_value = (mock_openai, "test-model")

    resp = client.post("/api/analyse", json={"known_site": "freepik"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["known_site"]["is_aggregator"] is True
    assert data["known_site"]["stacked_terms_note"]
    assert "Flux" in data["known_site"]["underlying_models"]


def test_analyse_with_unknown_site_slug(client):
    resp = client.post("/api/analyse", json={"known_site": "totally_made_up"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


@patch("src.routes.firecrawl_discovery_crawl")
@patch("src.analysis._get_default_client")
def test_analyse_with_deep_discovery(mock_get_client, mock_discovery, client):
    """deep_discovery=True routes through firecrawl_discovery_crawl."""
    mock_discovery.return_value = {
        "combined_text": "Discovered policy text " * 200,
        "pages_crawled": [
            {"url": "https://newsite.com/terms", "type": "policy/terms page"},
            {"url": "https://newsite.com/privacy", "type": "policy/terms page"},
        ],
        "discovery_method": "firecrawl_map",
        "candidates_found": 5,
    }
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_AI_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_openai = MagicMock()
    mock_openai.chat.completions.create.return_value = mock_resp
    mock_get_client.return_value = (mock_openai, "test-model")

    resp = client.post("/api/analyse", json={
        "url": "https://newsite.com",
        "deep_discovery": True,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["discovery_method"] == "firecrawl_map"
    assert data["candidates_found"] == 5
    mock_discovery.assert_called_once()
