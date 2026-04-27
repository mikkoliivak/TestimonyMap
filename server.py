import csv
import io
import json
import os
import copy
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, Response
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


@app.route("/api/centers/summary")
def api_centers_summary():
    """Lightweight payload for the map: no testimony bodies, just counts.
    Use /api/centers/<name> to lazy-load testimonies for one facility."""
    centers = load_centers()
    user_testimonies = load_user_testimonies()
    merged = merge_centers_with_user_testimonies(
        copy.deepcopy(centers), user_testimonies
    )
    summary = []
    for c in merged:
        summary.append({
            "name": c.get("name"),
            "lat": c.get("lat"),
            "lng": c.get("lng"),
            "operator": c.get("operator"),
            "city": c.get("city"),
            "testimony_count": len(c.get("testimonies", [])),
        })
    return jsonify(summary)


@app.route("/api/centers/<path:name>")
def api_center_detail(name):
    centers = load_centers()
    user_testimonies = load_user_testimonies()
    merged = merge_centers_with_user_testimonies(
        copy.deepcopy(centers), user_testimonies
    )
    for c in merged:
        if c.get("name") == name:
            return jsonify(c)
    return jsonify({"error": "not found"}), 404


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


@app.route("/api/export/csv")
def api_export_csv():
    centers = load_centers()
    user_testimonies = load_user_testimonies()
    merged = merge_centers_with_user_testimonies(copy.deepcopy(centers), user_testimonies)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "facility_name", "lat", "lng", "operator", "address", "osm_id",
        "statement", "date", "source", "publisher", "article_title",
        "search_keywords", "matched_noise_word", "facility_hints", "submitted",
    ])
    for center in merged:
        base = [
            center.get("name", ""),
            center.get("lat", ""),
            center.get("lng", ""),
            center.get("operator", ""),
            center.get("address", ""),
            center.get("osm_id", ""),
        ]
        for t in center.get("testimonies", []):
            search_keywords = t.get("search_keywords") or ([t.get("search_keyword")] if t.get("search_keyword") else [])
            facility_hints = t.get("facility_hints") or ([t.get("facility_hint")] if t.get("facility_hint") else [])
            writer.writerow(base + [
                t.get("statement", ""),
                t.get("date", ""),
                t.get("source", ""),
                t.get("publisher", t.get("source-details", "")),
                t.get("article_title", ""),
                "; ".join(search_keywords),
                t.get("matched_noise_word", ""),
                "; ".join(facility_hints),
                "yes" if t.get("submitted") else "no",
            ])

    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=testimonies.csv"},
    )


if __name__ == "__main__":
    os.makedirs(STATIC_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=5002, debug=True)
