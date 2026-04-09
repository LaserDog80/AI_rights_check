"""Flask route handlers for the AI Terms Analyzer."""

import json
import os

import requests
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv, set_key

from .extraction import fetch_terms_text, extract_text_from_file, MAX_TEXT_LENGTH
from .analysis import analyse_terms, deep_analyse_terms, tier_compare_terms
from .crawl import ai_crawl, firecrawl_discovery_crawl, known_site_crawl
from . import firecrawl_client
from .known_sites import KNOWN_SITES, get_site, list_sites

app = Flask(__name__, template_folder="../templates")


def _get_api_config():
    """Extract optional API configuration from the request JSON or form data."""
    if request.is_json:
        data = request.get_json(force=True)
    else:
        data = {}
    return {
        "api_key": data.get("api_key", ""),
        "base_url": data.get("api_base_url", ""),
        "model": data.get("api_model", ""),
    }


def _get_terms_text(data: dict, api_config: dict):
    """Extract terms text from a URL, raw text, known site, or deep crawl.

    Returns a 4-tuple: ``(text, source_label, pages_list, extras_dict)``.
    The ``extras_dict`` carries metadata that should be merged into the API
    response (e.g. ``known_site`` info for aggregator warnings).
    """
    url = data.get("url", "").strip()
    raw_text = data.get("raw_text", "").strip()
    known_site_slug = (data.get("known_site") or "").strip()
    use_deep_discovery = bool(data.get("deep_discovery", False))
    use_ai_crawl = bool(data.get("ai_crawl", False))

    extras: dict = {}

    # Mode 1: known curated site (dropdown selection)
    if known_site_slug:
        result = known_site_crawl(known_site_slug)
        if result.get("error"):
            raise ValueError(result["error"])
        text = result["combined_text"]
        site_info = result.get("known_site", {})
        if site_info:
            extras["known_site"] = site_info
        source = site_info.get("name") or known_site_slug
        return text, source, result.get("pages_crawled", []), extras

    # Mode 2: deep discovery via Firecrawl /map (unknown vendor URL)
    if url and use_deep_discovery:
        result = firecrawl_discovery_crawl(url)
        if result.get("error"):
            raise ValueError(result["error"])
        if "discovery_method" in result:
            extras["discovery_method"] = result["discovery_method"]
            extras["candidates_found"] = result.get("candidates_found", 0)
        return (
            result["combined_text"], url, result.get("pages_crawled", []), extras,
        )

    # Mode 3: legacy AI crawl
    if url and use_ai_crawl:
        result = ai_crawl(url, **api_config)
        if result.get("error"):
            raise ValueError(result["error"])
        return (
            result["combined_text"], url, result.get("pages_crawled", []), extras,
        )

    # Mode 4: single-URL fetch
    if url:
        text = fetch_terms_text(url)
        return text, url, [], extras

    # Mode 5: pasted text
    if raw_text:
        return raw_text[:MAX_TEXT_LENGTH], "pasted text", [], extras

    raise ValueError("Provide a URL, pick a known site, or paste the T&C text.")


def _attach_metadata(result: dict, source: str, text_len: int,
                      pages: list, extras: dict) -> dict:
    """Merge crawl metadata into an LLM analysis result."""
    result["source_url"] = source
    result["text_length"] = text_len
    if pages:
        result["pages_crawled"] = pages
    if extras:
        for key, val in extras.items():
            result[key] = val
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyse", methods=["POST"])
def api_analyse():
    data = request.get_json(force=True)
    api_config = _get_api_config()

    try:
        terms_text, source, pages, extras = _get_terms_text(data, api_config)

        if len(terms_text) < 100:
            return jsonify({"error": (
                "Could not extract enough text — the site may require JavaScript."
                " Try pasting the T&Cs directly or uploading a saved copy of the page."
            )}), 400

        result = analyse_terms(terms_text, **api_config)
        return jsonify(_attach_metadata(result, source, len(terms_text), pages, extras))

    except json.JSONDecodeError:
        return jsonify({"error": "AI returned invalid JSON. Please try again."}), 502
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {e}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/deep-analyse", methods=["POST"])
def api_deep_analyse():
    data = request.get_json(force=True)
    api_config = _get_api_config()
    tier = data.get("tier", "").strip()

    try:
        terms_text, source, pages, extras = _get_terms_text(data, api_config)

        if len(terms_text) < 100:
            return jsonify({"error": (
                "Could not extract enough text — the site may require JavaScript."
                " Try pasting the T&Cs directly or uploading a saved copy of the page."
            )}), 400

        result = deep_analyse_terms(terms_text, tier=tier, **api_config)
        return jsonify(_attach_metadata(result, source, len(terms_text), pages, extras))

    except json.JSONDecodeError:
        return jsonify({"error": "AI returned invalid JSON. Please try again."}), 502
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {e}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tier-compare", methods=["POST"])
def api_tier_compare():
    data = request.get_json(force=True)
    api_config = _get_api_config()

    try:
        terms_text, source, pages, extras = _get_terms_text(data, api_config)

        if len(terms_text) < 100:
            return jsonify({"error": (
                "Could not extract enough text — the site may require JavaScript."
                " Try pasting the T&Cs directly or uploading a saved copy of the page."
            )}), 400

        result = tier_compare_terms(terms_text, **api_config)
        return jsonify(_attach_metadata(result, source, len(terms_text), pages, extras))

    except json.JSONDecodeError:
        return jsonify({"error": "AI returned invalid JSON. Please try again."}), 502
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {e}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/known-sites", methods=["GET"])
def api_known_sites():
    """Return the curated list of image/video gen platforms for the dropdown."""
    return jsonify({
        "sites": list_sites(),
        "firecrawl_enabled": firecrawl_client.is_enabled(),
    })


@app.route("/api/save-firecrawl-key", methods=["POST"])
def api_save_firecrawl_key():
    """Persist the Firecrawl API key to .env so the running server picks it up."""
    data = request.get_json(force=True)
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write("")

    api_key = data.get("firecrawl_api_key", "").strip()
    if api_key:
        set_key(env_path, "FIRECRAWL_API_KEY", api_key)

    load_dotenv(env_path, override=True)
    firecrawl_client.reset_client()

    return jsonify({"status": "saved", "enabled": firecrawl_client.is_enabled()})


@app.route("/api/save-config", methods=["POST"])
def api_save_config():
    """Save API configuration to .env file."""
    data = request.get_json(force=True)
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

    # Create .env if it doesn't exist
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write("")

    api_key = data.get("api_key", "").strip()
    base_url = data.get("api_base_url", "").strip()
    model = data.get("api_model", "").strip()

    if api_key:
        set_key(env_path, "NEBIUS_API_KEY", api_key)
    if base_url:
        set_key(env_path, "NEBIUS_BASE_URL", base_url)
    if model:
        set_key(env_path, "NEBIUS_MODEL", model)

    # Reload so the running server picks up changes
    load_dotenv(env_path, override=True)

    # Reset the cached default client so it picks up new values
    from .analysis import _get_default_client
    import src.analysis as _analysis
    _analysis._default_client = None
    _analysis._default_model = None

    return jsonify({"status": "saved"})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Handle file upload, extract text, and run the requested analysis."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected."}), 400

    mode = request.form.get("mode", "quick")
    tier = request.form.get("tier", "")
    api_key = request.form.get("api_key", "")
    api_base_url = request.form.get("api_base_url", "")
    api_model = request.form.get("api_model", "")
    api_config = {"api_key": api_key, "base_url": api_base_url, "model": api_model}

    try:
        terms_text = extract_text_from_file(file)

        if len(terms_text) < 100:
            return jsonify({"error": "Could not extract enough text from the file."}), 400

        if mode == "deep":
            result = deep_analyse_terms(terms_text, tier=tier, **api_config)
        elif mode == "tier-compare":
            result = tier_compare_terms(terms_text, **api_config)
        else:
            result = analyse_terms(terms_text, **api_config)

        result["source_url"] = f"uploaded: {file.filename}"
        result["text_length"] = len(terms_text)
        return jsonify(result)

    except json.JSONDecodeError:
        return jsonify({"error": "AI returned invalid JSON. Please try again."}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500
