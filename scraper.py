"""
News scraper for data-center noise testimonies.
Pipeline: config → search → fetch → filter → save → merge
Source: Bing News RSS (direct URLs, no API key needed).
"""

import math
import re
import json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus, parse_qs, urlparse, unquote

import requests
import trafilatura

# ── CONFIG ────────────────────────────────────────────────────────

# Generic topic terms; each center name (lowercased) is also a topic/merge string from FACILITIES.
BASE_TOPIC_WORDS = [
    "data center", "datacenter", "server farm", "computing facility",
    "crypto", "cryptocurrency", "bitcoin", "mining", "mining facility",
]


def load_facilities_from_centers(centers_path=None) -> dict:
    """One FACILITIES entry per center in centers.json: search + merge use the facility name only."""
    path = Path(centers_path) if centers_path else Path(__file__).resolve().parent / "centers.json"
    if not path.is_file():
        raise FileNotFoundError(f"centers file not found: {path}")
    with open(path, encoding="utf-8") as f:
        centers = json.load(f)
    out = {}
    for c in centers:
        name = (c.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        out[name] = {
            "search_names": [key],
            "merge_keywords": [key],
        }
    return out


FACILITIES = load_facilities_from_centers()


def _compile_topic_re(facilities: dict):
    words = list(BASE_TOPIC_WORDS)
    for info in facilities.values():
        for kw in info["merge_keywords"]:
            if len(kw) >= 2:
                words.append(kw)
    uniq = []
    seen = set()
    for w in sorted(set(words), key=len, reverse=True):
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    return re.compile(r"(" + "|".join(re.escape(w) for w in uniq) + r")", re.I)


# EPA Noise Control Act + WHO Environmental Noise Guidelines
IMPACT_TERMS = [
    "noise", "noise complaint", "noise pollution",
    "health effects noise", "sleep disturbance",
    "residents complaints", "decibel", "noise ordinance",
]

# Passage must contain ≥1 noise word AND ≥1 topic word
NOISE_WORDS = [
    "noise", "noisy", "loud", "loudness", "roar", "roaring", "hum", "humming",
    "buzz", "buzzing", "drone", "droning", "rumble", "rumbling", "whine",
    "racket", "din", "blaring",
    "hear", "heard", "hearing", "sound", "sounds", "audible", "inaudible",
    "quiet", "silence", "deafening",
    "decibel", "dba", "db(a)", "db", "noise level", "sound level",
    "sound pressure", "low-frequency", "infrasound",
    "sleep disturbance", "sleep disruption", "insomnia", "migraine",
    "headache", "tinnitus", "annoyance", "stress",
    "noise ordinance", "noise regulation", "noise limit", "noise code",
    "noise complaint", "noise pollution", "noise control", "noise violation",
    "noise permit", "sound barrier", "sound wall",
]

NOISE_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in NOISE_WORDS) + r")\b", re.I)
TOPIC_RE = _compile_topic_re(FACILITIES)

MAX_ARTICLES_PER_QUERY = 10
MAX_WORKERS = 8


def reload_facilities():
    """Re-read centers.json into module globals (call after OSM update)."""
    global FACILITIES, TOPIC_RE
    FACILITIES = load_facilities_from_centers()
    TOPIC_RE = _compile_topic_re(FACILITIES)

# ── SEARCH ────────────────────────────────────────────────────────

def generate_queries():
    queries, seen = [], set()
    for name, info in FACILITIES.items():
        for search_name in info["search_names"]:
            for term in IMPACT_TERMS:
                q = f"{search_name} {term}"
                if q not in seen:
                    seen.add(q)
                    queries.append((q, name))
    return queries


def search_bing_news(keyword, max_items=MAX_ARTICLES_PER_QUERY):
    url = f"https://www.bing.com/news/search?q={quote_plus(keyword)}&format=rss"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, timeout=15, headers=headers)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception as e:
        print(f"  [skip] '{keyword}': {e}")
        return []

    ns_match = re.search(r'xmlns:News="([^"]+)"', resp.text)
    ns = ns_match.group(1) if ns_match else None

    items = []
    for item in root.iter("item"):
        if len(items) >= max_items:
            break
        raw_link = (item.findtext("link") or "").strip()
        if "apiclick.aspx" in raw_link:
            real = parse_qs(urlparse(raw_link).query).get("url", [""])[0]
            link = unquote(real) if real else raw_link
        else:
            link = raw_link
        if not link.startswith("http"):
            continue

        title = (item.findtext("title") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        date_str = ""
        if pub_date:
            try:
                date_str = parsedate_to_datetime(pub_date).strftime("%m-%d-%Y")
            except Exception:
                date_str = pub_date

        publisher = ""
        if ns:
            publisher = (item.findtext(f"{{{ns}}}Source") or "").strip()
        if not publisher:
            publisher = urlparse(link).netloc.replace("www.", "").split(".")[0].title()

        items.append({"link": link, "title": title, "date": date_str, "publisher": publisher})
    return items

# ── FETCH ─────────────────────────────────────────────────────────

def fetch_and_extract(url):
    try:
        html = trafilatura.fetch_url(url)
        if not html:
            return url, ""
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
        return url, (text or "").strip()
    except Exception:
        return url, ""


def fetch_all(urls):
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_and_extract, u): u for u in urls}
        for fut in as_completed(futures):
            url, text = fut.result()
            results[url] = text
    return results

# ── FILTER ────────────────────────────────────────────────────────

def find_relevant_passages(text, title=""):
    """Topic match uses article title + excerpt so headlines that name the site still qualify."""
    title = (title or "").strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    passages, seen = [], set()
    for i, sent in enumerate(sentences):
        if not NOISE_RE.search(sent):
            continue
        start = max(0, i - 1)
        end = min(len(sentences), i + 2)
        block = re.sub(r"\s+", " ", " ".join(sentences[start:end])).strip()
        if len(block) < 30 or len(block) > 2000:
            continue
        topic_haystack = (title + " " + block).strip()
        if not (NOISE_RE.search(block) and TOPIC_RE.search(topic_haystack)):
            continue
        key = block[:200]
        if key not in seen:
            seen.add(key)
            passages.append(block)
    return passages

# ── SAVE + MERGE ──────────────────────────────────────────────────

def run_scraper(save_path="scraped_testimonies.json"):
    queries = generate_queries()
    print(f"Generated {len(queries)} queries ({len(FACILITIES)} facilities × {len(IMPACT_TERMS)} terms)\n")

    articles = {}
    for query, facility in queries:
        print(f"  searching: '{query}'")
        for art in search_bing_news(query):
            url = art["link"]
            if url not in articles:
                articles[url] = {**art, "search_keyword": query, "facility_hint": facility}

    print(f"\nFound {len(articles)} unique articles. Fetching...\n")
    texts = fetch_all(articles.keys())
    print(f"Fetched {sum(1 for t in texts.values() if t)}/{len(articles)} articles\n")

    testimonies, seen = [], set()
    for url, meta in articles.items():
        text = texts.get(url, "")
        if not text:
            continue
        for passage in find_relevant_passages(text, title=meta.get("title") or ""):
            key = passage[:200]
            if key in seen:
                continue
            seen.add(key)
            testimonies.append({
                "statement": passage,
                "date": meta["date"] or "Unknown",
                "source": url,
                "source-details": meta["publisher"] or "Unknown",
                "publisher": meta["publisher"] or "Unknown",
                "article_title": meta["title"],
                "search_keyword": meta["search_keyword"],
                "facility_hint": meta.get("facility_hint"),
                "search_source": "bing_news_rss",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            })

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(testimonies, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(testimonies)} testimonies to {save_path}")
    return testimonies


def merge_into_centers(centers_path="centers.json", scraped_path="scraped_testimonies.json"):
    try:
        with open(centers_path) as f:
            centers = json.load(f)
        with open(scraped_path) as f:
            scraped = json.load(f)
    except FileNotFoundError as e:
        print(f"[merge] File not found: {e}")
        return

    name_to_idx = {c["name"]: i for i, c in enumerate(centers)}
    existing = {
        c["name"]: {t["statement"].strip() for t in c.get("testimonies", []) if t.get("statement")}
        for c in centers
    }

    def pick_facility_for_merge(text: str):
        """Assign to the facility whose merge keyword is the longest substring match."""
        text_l = text.lower()
        best_name, best_len = None, 0
        for name, info in FACILITIES.items():
            for kw in info["merge_keywords"]:
                if kw in text_l and len(kw) > best_len:
                    best_len = len(kw)
                    best_name = name
        return best_name

    added = 0
    for t in scraped:
        stmt = re.sub(r"\s+", " ", re.sub(r"\bAdvertisement\b", "", t.get("statement", ""))).strip()
        if len(stmt) < 30:
            continue
        hint = (t.get("facility_hint") or "").strip()
        if hint in name_to_idx:
            target = hint
        else:
            text = (
                stmt
                + " "
                + (t.get("source") or "")
                + " "
                + (t.get("article_title") or "")
            )
            target = pick_facility_for_merge(text)
        if not target or target not in name_to_idx:
            continue
        if any(stmt in ex or ex in stmt for ex in existing[target]):
            continue
        t["statement"] = stmt
        centers[name_to_idx[target]].setdefault("testimonies", []).append(t)
        existing[target].add(stmt)
        added += 1

    if added:
        with open(centers_path, "w", encoding="utf-8") as f:
            json.dump(centers, f, indent=2, ensure_ascii=False)
    print(f"[merge] Added {added} new testimonies into {centers_path}")


# ── OSM UPDATE ───────────────────────────────────────────────────

OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
OVERPASS_QUERY = """
[out:json][timeout:60];
(
  nwr["telecom"="data_center"](24.5,-125.0,49.5,-66.5);
);
out center;
"""

# ~0.5 km — close enough to be the same facility
_DEDUP_KM = 0.5


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _find_existing(center, existing_centers):
    """Match by name+proximity or proximity alone."""
    name = center["name"].lower()
    for i, ec in enumerate(existing_centers):
        ec_name = ec["name"].lower()
        dist = _haversine_km(center["lat"], center["lng"], ec["lat"], ec["lng"])
        # Same coords (< 0.5 km) → same facility
        if dist < _DEDUP_KM:
            return i
        # Same name and within 5 km (accounts for minor coordinate drift)
        if name and ec_name and name == ec_name and dist < 5:
            return i
    return None


def update_centers_from_osm(centers_path="centers.json"):
    """Fetch data centers from OpenStreetMap and merge new ones into centers.json."""
    path = Path(centers_path)
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            centers = json.load(f)
    else:
        centers = []

    print("[osm] Querying Overpass API for US data centers...")
    elements = None
    for url in OVERPASS_URLS:
        try:
            print(f"  [osm] Trying {url} ...")
            resp = requests.post(url, data={"data": OVERPASS_QUERY}, timeout=180)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            break
        except Exception as e:
            print(f"  [osm] Failed: {e}")
    if elements is None:
        print("[osm] All Overpass servers failed, skipping OSM update")
        return centers

    print(f"[osm] Got {len(elements)} elements from OSM")

    added = 0
    for el in elements:
        tags = el.get("tags", {})
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        name = (tags.get("name") or "").strip()
        if not lat or not lon:
            continue
        if not name:
            # Fall back to operator as name so the scraper has something to search
            name = (tags.get("operator") or "").strip()
        if not name:
            continue

        osm_center = {"name": name, "lat": lat, "lng": lon}

        # Add optional OSM metadata
        if tags.get("operator"):
            osm_center["operator"] = tags["operator"]
        if tags.get("addr:full") or tags.get("addr:street"):
            osm_center["address"] = tags.get("addr:full") or tags.get("addr:street")
        if tags.get("website") or tags.get("contact:website"):
            osm_center["website"] = tags.get("website") or tags.get("contact:website")

        idx = _find_existing(osm_center, centers)
        if idx is not None:
            # Update metadata on existing entry, but never overwrite testimonies or county
            existing = centers[idx]
            for key in ("operator", "address", "website"):
                if osm_center.get(key) and not existing.get(key):
                    existing[key] = osm_center[key]
        else:
            centers.append(osm_center)
            added += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(centers, f, indent=2, ensure_ascii=False)
    print(f"[osm] {added} new centers added, {len(centers)} total in {centers_path}")
    return centers


if __name__ == "__main__":
    update_centers_from_osm()
    reload_facilities()
    run_scraper()
    merge_into_centers()
