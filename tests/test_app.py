"""Tests for the AI Terms Analyzer app."""

import json
from unittest.mock import MagicMock, patch

import pytest

import app as analyzer_app


@pytest.fixture
def client():
    analyzer_app.app.config["TESTING"] = True
    with analyzer_app.app.test_client() as c:
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


@patch.object(analyzer_app, "client")
def test_analyse_with_raw_text(mock_client, client):
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_AI_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp

    long_text = "Terms and Conditions: " + "a " * 200
    resp = client.post("/api/analyse", json={"raw_text": long_text})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["platform_name"] == "TestAI"
    assert data["classification"] == "Moderate"
    assert len(data["checklist"]) == 2


@patch.object(analyzer_app, "fetch_terms_text", return_value="Terms " * 100)
@patch.object(analyzer_app, "client")
def test_analyse_with_url(mock_client, mock_fetch, client):
    mock_choice = MagicMock()
    mock_choice.message.content = MOCK_AI_RESPONSE
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp

    resp = client.post("/api/analyse", json={"url": "https://example.com/terms"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["source_url"] == "https://example.com/terms"
