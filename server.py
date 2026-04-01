import json
import os
import copy
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

APP_DIR = Path(__file__).resolve().parent
CENTERS_PATH = APP_DIR / "centers.json"
USER_TESTIMONIES_PATH = APP_DIR / "user_testimonies.json"
STATIC_DIR = APP_DIR / "web" / "dist"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})


def load_centers():
    try:
        with open(CENTERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_user_testimonies():
    try:
        with open(USER_TESTIMONIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_user_testimonies(data):
    with open(USER_TESTIMONIES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def merge_centers_with_user_testimonies(centers, user_list):
    """Add user-submitted testimonies into the right facility by name."""
    name_to_idx = {c.get("name"): i for i, c in enumerate(centers)}
    for item in user_list:
        facility = (item.get("facility") or "").strip()
        if not facility or facility not in name_to_idx:
            continue
        idx = name_to_idx[facility]
        testimony = {
            "statement": (item.get("statement") or "").strip(),
            "date": (item.get("date") or "Unknown").strip() or "Unknown",
            "source": (item.get("source") or "").strip() or "",
            "source-details": (item.get("source-details") or "Community submission").strip(),
            "submitted": True,
        }
        if testimony["statement"]:
            centers[idx].setdefault("testimonies", []).append(testimony)
    return centers


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    # Serve static assets; otherwise SPA fallback for client-side routes
    file_path = STATIC_DIR / path
    if file_path.is_file():
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/centers")
def api_centers():
    centers = load_centers()
    user_testimonies = load_user_testimonies()
    merged = merge_centers_with_user_testimonies(
        copy.deepcopy(centers), user_testimonies
    )
    return jsonify(merged)


@app.route("/api/testimonies", methods=["POST"])
def api_add_testimony():
    data = request.get_json(force=True, silent=True) or {}
    facility = (data.get("facility") or "").strip()
    statement = (data.get("statement") or "").strip()
    if not facility or not statement:
        return jsonify({"ok": False, "error": "facility and statement are required"}), 400
    user_list = load_user_testimonies()
    user_list.append({
        "facility": facility,
        "statement": statement,
        "date": (data.get("date") or "").strip() or "Unknown",
        "source": (data.get("source") or "").strip() or "",
        "source-details": (data.get("source-details") or "Community submission").strip(),
    })
    save_user_testimonies(user_list)
    return jsonify({"ok": True})


if __name__ == "__main__":
    os.makedirs(STATIC_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=5002, debug=True)
