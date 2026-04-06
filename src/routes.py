"""Flask route handlers for the AI Terms Analyzer."""

import json
import os

import requests
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv, set_key

from .extraction import fetch_terms_text, extract_text_from_file, MAX_TEXT_LENGTH
from .analysis import analyse_terms, deep_analyse_terms, tier_compare_terms
from .crawl import ai_crawl

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


def _get_terms_text(data: dict, api_config: dict) -> str:
    """Extract terms text from URL, raw text, or AI-assisted crawl."""
    url = data.get("url", "").strip()
    raw_text = data.get("raw_text", "").strip()
    use_ai_crawl = data.get("ai_crawl", False)

    if url and use_ai_crawl:
        result = ai_crawl(url, **api_config)
        if result.get("error"):
            raise ValueError(result["error"])
        text = result["combined_text"]
        return text, url, result.get("pages_crawled", [])
    elif url:
        text = fetch_terms_text(url)
        return text, url, []
    elif raw_text:
        return raw_text[:MAX_TEXT_LENGTH], "pasted text", []
    else:
        raise ValueError("Provide a URL or paste the T&C text.")


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
        terms_text, source, pages = _get_terms_text(data, api_config)

        if len(terms_text) < 100:
            return jsonify({"error": (
                "Could not extract enough text — the site may require JavaScript."
                " Try pasting the T&Cs directly or uploading a saved copy of the page."
            )}), 400

        result = analyse_terms(terms_text, **api_config)
        result["source_url"] = source
        result["text_length"] = len(terms_text)
        if pages:
            result["pages_crawled"] = pages
        return jsonify(result)

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
        terms_text, source, pages = _get_terms_text(data, api_config)

        if len(terms_text) < 100:
            return jsonify({"error": (
                "Could not extract enough text — the site may require JavaScript."
                " Try pasting the T&Cs directly or uploading a saved copy of the page."
            )}), 400

        result = deep_analyse_terms(terms_text, tier=tier, **api_config)
        result["source_url"] = source
        result["text_length"] = len(terms_text)
        if pages:
            result["pages_crawled"] = pages
        return jsonify(result)

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
        terms_text, source, pages = _get_terms_text(data, api_config)

        if len(terms_text) < 100:
            return jsonify({"error": (
                "Could not extract enough text — the site may require JavaScript."
                " Try pasting the T&Cs directly or uploading a saved copy of the page."
            )}), 400

        result = tier_compare_terms(terms_text, **api_config)
        result["source_url"] = source
        result["text_length"] = len(terms_text)
        if pages:
            result["pages_crawled"] = pages
        return jsonify(result)

    except json.JSONDecodeError:
        return jsonify({"error": "AI returned invalid JSON. Please try again."}), 502
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {e}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
