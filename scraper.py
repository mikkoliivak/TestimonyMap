"""
News scraper for data-center noise testimonies.
Pipeline: config → search → fetch → filter → save → merge
Source: Bing News RSS (direct URLs, no API key needed).
"""

import re
import json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, parse_qs, urlparse, unquote

import requests
import trafilatura

# ── CONFIG ────────────────────────────────────────────────────────

FACILITIES = {
    "Greenidge": {
        "search_names": ["greenidge", "greenidge generation"],
        "merge_keywords": ["greenidge", "dresden"],
    },
    "Lake Mariner": {
        "search_names": ["lake mariner", "terawulf lake mariner"],
        "merge_keywords": ["lake mariner", "somerset", "terawulf"],
    },
    "H5 Datacenters": {
        "search_names": ["h5 datacenters"],
        "merge_keywords": ["h5 datacenters", "h5 data", "h5"],
    },
    "Blockfusion (Niagara Falls)": {
        "search_names": ["blockfusion niagara falls", "niagara falls crypto mining"],
        "merge_keywords": ["blockfusion", "niagara falls"],
    },
}

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

TOPIC_WORDS = [
    "data center", "datacenter", "server farm", "computing facility",
    "crypto", "cryptocurrency", "bitcoin", "mining", "mining facility",
    "greenidge", "lake mariner", "somerset", "niagara", "terawulf",
    "blockfusion", "h5 data",
]

NOISE_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in NOISE_WORDS) + r")\b", re.I)
TOPIC_RE = re.compile(r"(" + "|".join(re.escape(w) for w in TOPIC_WORDS) + r")", re.I)

MAX_ARTICLES_PER_QUERY = 10
MAX_WORKERS = 8

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

def find_relevant_passages(text):
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
        if not (NOISE_RE.search(block) and TOPIC_RE.search(block)):
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
        for passage in find_relevant_passages(text):
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

    added = 0
    for t in scraped:
        stmt = re.sub(r"\s+", " ", re.sub(r"\bAdvertisement\b", "", t.get("statement", ""))).strip()
        if len(stmt) < 30:
            continue
        text = (stmt + " " + t.get("source", "")).lower()
        target = next((name for name, info in FACILITIES.items()
                       if any(kw in text for kw in info["merge_keywords"])), None)
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


if __name__ == "__main__":
    run_scraper()
    merge_into_centers()
