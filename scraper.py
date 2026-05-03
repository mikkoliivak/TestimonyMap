"""Scrape data-center noise testimonies from Bing News RSS."""

import math
import os
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


def _atomic_write_json(path, data):
    """Write JSON atomically: write to a tmp file then rename, so a crash mid-write
    can't leave centers.json or scraped_testimonies.json half-written."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

BASE_TOPIC_WORDS = [
    "data center", "data centre", "datacenter", "datacentre",
    "server farm", "computing facility",
    "crypto", "cryptocurrency", "bitcoin", "mining", "mining facility",
]

GENERIC_NAMES = {
    "data center", "data centre", "datacenter", "datacentre",
    "server farm", "computing facility", "data hall",
    "dc", "facility", "telecom", "telecommunications",
    "data center building", "datacenter building",
}


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _is_generic_name(name: str) -> bool:
    n = _normalize_name(name)
    if not n:
        return True
    return n in GENERIC_NAMES


def load_facilities_from_centers(centers_path=None) -> dict:
    """One FACILITIES entry per center in centers.json: search + merge use the facility name only."""
    path = Path(centers_path) if centers_path else Path(__file__).resolve().parent / "centers.json"
    if not path.is_file():
        raise FileNotFoundError(f"centers file not found: {path}")
    with open(path, encoding="utf-8") as f:
        raw = f.read().strip()
    centers = json.loads(raw) if raw else []
    out = {}
    for c in centers:
        name = (c.get("name") or "").strip()
        if not name or _is_generic_name(name):
            continue
        key = _normalize_name(name)
        # If two centers share a name (rare, but possible), keep the first; both
        # still live in centers.json — only one is used as a search target.
        if name in out:
            continue
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


IMPACT_TERMS = [
    "noise", "noise complaint", "noise pollution",
    "health effects noise", "sleep disturbance",
    "residents complaints", "decibel", "noise ordinance",
]

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

MAX_ARTICLES_PER_QUERY = 25
MAX_WORKERS = 8


def reload_facilities():
    """Re-read centers.json into module globals (call after OSM update)."""
    global FACILITIES, TOPIC_RE
    FACILITIES = load_facilities_from_centers()
    TOPIC_RE = _compile_topic_re(FACILITIES)

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
    urls = list(urls)
    total = len(urls)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(fetch_and_extract, u): u for u in urls}
        done = 0
        for fut in as_completed(futures):
            url, text = fut.result()
            results[url] = text
            done += 1
            # Print on every 1% increment (or every article if there are few)
            step = max(1, total // 100)
            if done % step == 0 or done == total:
                pct = (done / total) * 100 if total else 100
                ok = sum(1 for t in results.values() if t)
                print(f"  [fetch] {done}/{total} ({pct:.0f}%) — {ok} extracted")
    return results

def find_relevant_passages(text, title=""):
    """Topic match uses article title + excerpt so headlines that name the site still qualify.
    Returns list of (passage, matched_noise_word) tuples."""
    title = (title or "").strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    passages, seen = [], set()
    for i, sent in enumerate(sentences):
        noise_match = NOISE_RE.search(sent)
        if not noise_match:
            continue
        noise_word = noise_match.group(0).lower()
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
            passages.append((block, noise_word))
    return passages

def run_scraper(save_path="scraped_testimonies.json"):
    queries = generate_queries()
    print(f"Generated {len(queries)} queries ({len(FACILITIES)} facilities × {len(IMPACT_TERMS)} terms)\n")

    # Run Bing News searches in parallel — each search is a network round-trip,
    # so threading gives a ~MAX_WORKERS× speedup over the sequential loop.
    articles = {}
    completed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_meta = {
            pool.submit(search_bing_news, q): (q, facility) for q, facility in queries
        }
        for fut in as_completed(future_to_meta):
            query, facility = future_to_meta[fut]
            completed += 1
            if completed % 50 == 0 or completed == len(queries):
                print(f"  [search] {completed}/{len(queries)} queries done")
            try:
                results = fut.result()
            except Exception as e:
                print(f"  [skip] '{query}': {e}")
                continue
            for art in results:
                url = art["link"]
                if url not in articles:
                    articles[url] = {**art, "search_keywords": [query], "facility_hints": [facility]}
                else:
                    if query not in articles[url]["search_keywords"]:
                        articles[url]["search_keywords"].append(query)
                    if facility not in articles[url]["facility_hints"]:
                        articles[url]["facility_hints"].append(facility)

    print(f"\nFound {len(articles)} unique articles. Fetching...\n")
    texts = fetch_all(articles.keys())
    print(f"Fetched {sum(1 for t in texts.values() if t)}/{len(articles)} articles\n")

    # Article-centric output: one record per article, with sections as children
    output, seen_passages = [], set()
    for url, meta in articles.items():
        text = texts.get(url, "")
        if not text:
            continue
        sections = []
        for passage, noise_word in find_relevant_passages(text, title=meta.get("title") or ""):
            key = passage[:200]
            if key in seen_passages:
                continue
            seen_passages.add(key)
            sections.append({"statement": passage, "matched_noise_word": noise_word})
        if not sections:
            continue
        output.append({
            "article_url": url,
            "article_title": meta["title"],
            "date": meta["date"] or "Unknown",
            "publisher": meta["publisher"] or "Unknown",
            "search_keywords": meta["search_keywords"],
            "facility_hints": meta["facility_hints"],
            "search_source": "bing_news_rss",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "sections": sections,
        })

    _atomic_write_json(save_path, output)
    total_sections = sum(len(a["sections"]) for a in output)
    print(f"Saved {len(output)} articles ({total_sections} passages) to {save_path}")
    return output


def merge_into_centers(centers_path="centers.json", scraped_path="scraped_testimonies.json"):
    try:
        with open(centers_path) as f:
            raw = f.read().strip()
        centers = json.loads(raw) if raw else []
        with open(scraped_path) as f:
            scraped = json.load(f)
    except FileNotFoundError as e:
        print(f"[merge] File not found: {e}")
        return

    name_to_idx = {c["name"]: i for i, c in enumerate(centers)}
    # existing tracks individual statements (split on &&) for dedup
    existing = {}
    for c in centers:
        stmts = set()
        for t in c.get("testimonies", []):
            for s in (t.get("testimonies") or t.get("statement") or "").split("&&"):
                s = s.strip()
                if s:
                    stmts.add(s)
        existing[c["name"]] = stmts

    def _kw_pattern(kw: str):
        parts = [re.escape(p) for p in kw.split() if p]
        if not parts:
            return None
        return re.compile(r"\b" + r"\s+".join(parts) + r"\b", re.I)

    facility_patterns = {}
    for name, info in FACILITIES.items():
        pats = []
        for kw in info["merge_keywords"]:
            p = _kw_pattern(kw.strip().lower())
            if p:
                pats.append((kw, p))
        facility_patterns[name] = pats

    def evidence_for_facility(name: str, text: str) -> int:
        best = 0
        for kw, pat in facility_patterns.get(name, []):
            if pat.search(text):
                best = max(best, len(kw))
        return best

    def pick_facility_for_merge(statement_text: str, article_title: str, source_url: str):
        title_text = (article_title or "").strip().lower()
        stmt_text = (statement_text or "").strip().lower()
        source_text = (source_url or "").strip().lower()
        best_name, best_score = None, 0
        for name in FACILITIES:
            title_score = evidence_for_facility(name, title_text)
            stmt_score = evidence_for_facility(name, stmt_text)
            source_score = evidence_for_facility(name, source_text)
            score = max(title_score, stmt_score, source_score)
            if score > best_score:
                best_name, best_score = name, score
        return best_name, best_score

    added = 0
    for article in scraped:
        # Support both new article-centric format and legacy flat format
        if "sections" in article:
            sections = article.get("sections", [])
            title = article.get("article_title") or ""
            source = article.get("article_url") or ""
            date = article.get("date") or "Unknown"
            publisher = article.get("publisher") or "Unknown"
            hints = article.get("facility_hints") or []
            search_keywords = article.get("search_keywords") or []
            search_source = article.get("search_source", "bing_news_rss")
            retrieved_at = article.get("retrieved_at")
        else:
            # Legacy flat format
            sections = [{"statement": article.get("statement", ""), "matched_noise_word": article.get("matched_noise_word")}]
            title = article.get("article_title") or ""
            source = article.get("source") or ""
            date = article.get("date") or "Unknown"
            publisher = article.get("publisher") or "Unknown"
            hints = [article.get("facility_hint") or ""]
            search_keywords = [article.get("search_keyword") or ""]
            search_source = article.get("search_source", "bing_news_rss")
            retrieved_at = article.get("retrieved_at")

        # Collect valid new statements for this article grouped by target facility
        article_stmts: dict[str, list[str]] = {}
        for section in sections:
            stmt = re.sub(r"\s+", " ", re.sub(r"\bAdvertisement\b", "", section.get("statement", ""))).strip()
            if len(stmt) < 30:
                continue
            target, score = pick_facility_for_merge(stmt, title, source)
            for hint in hints:
                hint = hint.strip()
                if hint in name_to_idx:
                    hint_score = evidence_for_facility(hint, f"{title} {stmt}".lower())
                    if hint_score > 0:
                        target, score = hint, hint_score
                        break
            if not target or target not in name_to_idx:
                continue
            # Threshold scales with the facility name length: a 3-char facility ("AWS")
            # only needs the full 3-char word to match; longer names need ≥4 chars.
            min_score = max(3, min(len(_normalize_name(target)), 4))
            if score < min_score:
                continue
            if any(stmt in ex or ex in stmt for ex in existing[target]):
                continue
            article_stmts.setdefault(target, [])
            if not any(stmt in s or s in stmt for s in article_stmts[target]):
                article_stmts[target].append(stmt)

        # Store one record per article per facility, joining statements with &&
        for target, stmts in article_stmts.items():
            combined = " && ".join(stmts)
            # Check if an existing article record for this source already exists
            existing_articles = centers[name_to_idx[target]].setdefault("testimonies", [])
            article_record = next(
                (r for r in existing_articles if r.get("source") == source and r.get("article_title") == title),
                None,
            )
            if article_record:
                # Append new statements to existing article record
                existing_stmts = [s.strip() for s in article_record["testimonies"].split("&&")]
                new_stmts = [s for s in stmts if not any(s in ex or ex in s for ex in existing_stmts)]
                if new_stmts:
                    article_record["testimonies"] = " && ".join(existing_stmts + new_stmts)
                    added += len(new_stmts)
            else:
                record = {
                    "testimonies": combined,
                    "date": date,
                    "source": source,
                    "source-details": publisher,
                    "publisher": publisher,
                    "article_title": title,
                    "search_keywords": search_keywords,
                    "facility_hints": hints,
                    "search_source": search_source,
                    "retrieved_at": retrieved_at,
                }
                existing_articles.append(record)
                added += len(stmts)
            for stmt in stmts:
                existing[target].add(stmt)

    if added:
        _atomic_write_json(centers_path, centers)
    print(f"[merge] Added {added} new testimonies into {centers_path}")


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

_DEDUP_KM = 0.5


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _find_existing(center, existing_centers):
    """Match by OSM ID first, then fall back to normalized-name + proximity."""
    osm_id = center.get("osm_id")
    if osm_id is not None:
        for i, ec in enumerate(existing_centers):
            if ec.get("osm_id") == osm_id:
                return i
    name = _normalize_name(center.get("name", ""))
    for i, ec in enumerate(existing_centers):
        ec_name = _normalize_name(ec.get("name", ""))
        try:
            dist = _haversine_km(center["lat"], center["lng"], ec["lat"], ec["lng"])
        except (TypeError, KeyError):
            continue
        if dist < _DEDUP_KM:
            return i
        if name and ec_name and name == ec_name and dist < 5:
            return i
    return None


def update_centers_from_osm(centers_path="centers.json"):
    """Fetch data centers from OpenStreetMap and merge new ones into centers.json."""
    path = Path(centers_path)
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            raw = f.read().strip()
        centers = json.loads(raw) if raw else []
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
    skipped_generic = 0
    for el in elements:
        tags = el.get("tags", {})
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not lat or not lon:
            continue

        raw_name = (tags.get("name") or "").strip()
        operator = (tags.get("operator") or "").strip()
        city = (tags.get("addr:city") or "").strip()

        # Choose the most specific name available.
        if raw_name and not _is_generic_name(raw_name):
            name = raw_name
        elif operator and not _is_generic_name(operator):
            # Synthesize a useful name from operator (+ city for disambiguation)
            name = f"{operator} data center" + (f" ({city})" if city else "")
        else:
            skipped_generic += 1
            continue

        # Composite OSM identifier prevents collisions across node/way/relation namespaces.
        osm_type = el.get("type") or "node"
        osm_center = {
            "name": name,
            "lat": lat,
            "lng": lon,
            "osm_id": f"{osm_type}/{el.get('id')}",
        }

        if operator:
            osm_center["operator"] = operator
        if city:
            osm_center["city"] = city
        if tags.get("addr:full") or tags.get("addr:street"):
            osm_center["address"] = tags.get("addr:full") or tags.get("addr:street")
        if tags.get("website") or tags.get("contact:website"):
            osm_center["website"] = tags.get("website") or tags.get("contact:website")

        idx = _find_existing(osm_center, centers)
        if idx is not None:
            existing = centers[idx]
            for key in ("operator", "address", "website", "osm_id", "city"):
                if osm_center.get(key) and not existing.get(key):
                    existing[key] = osm_center[key]
            # If the existing entry still has a generic name and we now have a real one, upgrade it.
            if _is_generic_name(existing.get("name", "")) and not _is_generic_name(name):
                existing["name"] = name
        else:
            centers.append(osm_center)
            added += 1

    # Clean up any pre-existing entries whose name is generic (legacy data).
    before = len(centers)
    centers = [c for c in centers if not _is_generic_name(c.get("name", ""))]
    cleaned = before - len(centers)

    _atomic_write_json(path, centers)
    print(
        f"[osm] {added} new, {skipped_generic} skipped (generic name), "
        f"{cleaned} legacy generic entries removed, {len(centers)} total in {centers_path}"
    )
    return centers


if __name__ == "__main__":
    update_centers_from_osm()
    reload_facilities()
    run_scraper()
    merge_into_centers()
