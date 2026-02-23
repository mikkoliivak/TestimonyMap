# -*- coding: utf-8 -*-
"""
News testimony scraper with Selenium + BeautifulSoup.
Searches Yahoo News by keyword (Selenium loads JS), then extracts sound-related
quotes + context into testimonies (centers.json format).
"""

from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re
import json
import time
import pandas as pd

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# --- Config ---
# Focused queries: data centers / crypto sites + locations
KEYWORDS = [
    "data center noise greenidge",
    "crypto mining noise niagara falls",
    "bitcoin mine residents complaint",
    "terawulf lake mariner noise",
    "niagara falls data center noise residents",
    "ai data center residents noise",
]
SOUND_WORDS = [
    "noise", "sound", "loud", "hear", "heard", "decibel", "hum", "roar",
    "drone", "droning", "racket", "din", "quiet", "silence",
]
# Topic words so we only keep testimonies that mention both sound and
# datacenters/crypto/mining or the specific facilities/locations of interest.
TOPIC_WORDS = [
    "data center", "datacenter", "server farm",
    "crypto", "bitcoin", "mining",
    "greenidge", "lake mariner", "somerset", "niagara", "terawulf",
]
MAX_ARTICLES_PER_QUERY = 10
SENTENCES_BEFORE = 1
SENTENCES_AFTER = 1
DELAY_SECONDS = 2
WAIT_FOR_RESULTS_SEC = 5   # seconds to wait for Yahoo search results to load
# ------------------------------------------------


def get_driver():
    """Start Chrome in headless mode (no window). Install Chrome if needed."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    # Avoid "Chrome is being controlled by automated software"
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    try:
        driver = webdriver.Chrome(options=opts)
        return driver
    except Exception as e:
        print("Selenium: could not start Chrome. Install Chrome and try again:", e)
        raise


def search_yahoo_news(driver, keyword):
    """Load Yahoo News search with Selenium, then parse page source with BeautifulSoup."""
    query = quote_plus(keyword)
    url = "https://news.search.yahoo.com/search?p={}&ei=UTF-8".format(query)
    items = []
    try:
        driver.get(url)
        # Wait for results to appear (links in the main content)
        WebDriverWait(driver, WAIT_FOR_RESULTS_SEC).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href]"))
        )
        time.sleep(1)
        html = driver.page_source
    except Exception as e:
        print("  [skip] Yahoo search failed:", e)
        return items
    bs = BeautifulSoup(html, "html.parser")
    seen = set()
    for a in bs.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        if "search.yahoo.com" in href or "login." in href or "preferences" in href:
            continue
        if "yahoo.com" in href and "/news/" not in href and "/sports/" not in href and "finance.yahoo" not in href and "tech.yahoo" not in href:
            continue
        # Normalize
        if href.startswith("//"):
            href = "https:" + href
        if not href.startswith("http"):
            continue
        if href in seen:
            continue
        seen.add(href)
        title = a.get_text(strip=True) or ""
        if len(title) < 8:
            continue
        items.append({"link": href, "title": title, "pubdate": "", "description": ""})
        if len(items) >= MAX_ARTICLES_PER_QUERY:
            break
    return items


def normalize_date(pubdate_str):
    if not pubdate_str:
        return ""
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", pubdate_str)
    if m:
        a, b, c = m.groups()
        if len(c) == 2:
            c = "20" + c
        return "{}-{}-{}".format(a, b, c)
    return ""


def source_name(url):
    url = url.lower()
    if "yahoo.com" in url:
        if "finance" in url:
            return "Yahoo Finance"
        if "tech" in url:
            return "Yahoo Tech"
        return "Yahoo News"
    m = re.search(r"https?://(?:www\.)?([^./]+)", url)
    return m.group(1).title() if m else "Unknown"


def split_sentences(text):
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def get_context(sentences, idx, before=1, after=1):
    start = max(0, idx - before)
    end = min(len(sentences), idx + after + 1)
    return " ".join(sentences[start:end]).strip()


def extract_quotes_from_article(driver, url, rss_description=""):
    """Load article with Selenium, parse with BeautifulSoup, extract sound quotes + context."""
    sound_pat = re.compile(
        r"\b(" + "|".join(re.escape(w) for w in SOUND_WORDS) + r")\b", re.I
    )
    topic_pat = re.compile(
        r"(" + "|".join(re.escape(w) for w in TOPIC_WORDS) + r")", re.I
    )
    testimonies = []
    try:
        driver.get(url)
        time.sleep(1)
        html = driver.page_source
    except Exception as e:
        print("    [skip] Could not fetch:", e)
        return testimonies
    bs = BeautifulSoup(html, "html.parser")
    for tag in bs(["script", "style"]):
        tag.decompose()
    text = bs.get_text(separator=" ", strip=True)
    sentences = split_sentences(text)
    seen = set()

    def add(block):
        block = re.sub(r"\s+", " ", block).strip()
        if len(block) < 30 or len(block) > 2000:
            return
        # Require at least one sound word AND one topic word
        if not (sound_pat.search(block) and topic_pat.search(block)):
            return
        key = block[:250]
        if key in seen:
            return
        seen.add(key)
        testimonies.append(block)

    for i, sent in enumerate(sentences):
        if not sound_pat.search(sent):
            continue
        add(get_context(sentences, i, before=SENTENCES_BEFORE, after=SENTENCES_AFTER))

    for m in re.finditer(r'"([^"]{20,600})"', text):
        quoted = m.group(1).strip()
        for i, sent in enumerate(sentences):
            if quoted[:20] in sent or quoted[-20:] in sent:
                add(get_context(sentences, i, before=SENTENCES_BEFORE, after=SENTENCES_AFTER))
                break
        else:
            add(quoted)

    for bq in bs.find_all("blockquote"):
        t = bq.get_text(separator=" ", strip=True)
        if 30 < len(t) < 1500:
            add(t)

    if rss_description and 30 < len(rss_description) < 800:
        if sound_pat.search(rss_description) or "said" in rss_description.lower():
            add(rss_description)

    return testimonies


def run_scraper(save_path="scraped_testimonies.json"):
    driver = None
    try:
        driver = get_driver()
        all_testimonies = []
        seen = set()
        for kw in KEYWORDS:
            print("Searching Yahoo News: '{}'".format(kw))
            items = search_yahoo_news(driver, kw)
            print("  Found {} articles".format(len(items)))
            time.sleep(DELAY_SECONDS)
            for art in items:
                link = art["link"]
                pub = normalize_date(art["pubdate"])
                src = source_name(link)
                quotes = extract_quotes_from_article(driver, link, art.get("description", ""))
                for st in quotes:
                    st = st.strip()
                    if not st or len(st) < 25:
                        continue
                    key = st[:200]
                    if key in seen:
                        continue
                    seen.add(key)
                    all_testimonies.append({
                        "statement": st,
                        "date": pub or "Unknown",
                        "source": link,
                        "source-details": src,
                    })
                time.sleep(DELAY_SECONDS)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(all_testimonies, f, indent=2, ensure_ascii=False)
        print("\nSaved {} testimonies to {}".format(len(all_testimonies), save_path))
        return all_testimonies
    finally:
        if driver:
            driver.quit()


def merge_into_centers(
    centers_path="centers.json",
    scraped_path="scraped_testimonies.json",
):
    """
    Load existing centers.json and scraped_testimonies.json, and append
    new testimonies under the appropriate datacenter based on keywords.
    Existing statements are not duplicated.
    """
    try:
        with open(centers_path, "r", encoding="utf-8") as f:
            centers = json.load(f)
    except FileNotFoundError:
        print(f"[merge] centers file not found at {centers_path}, skipping merge.")
        return
    try:
        with open(scraped_path, "r", encoding="utf-8") as f:
            scraped = json.load(f)
    except FileNotFoundError:
        print(f"[merge] scraped testimonies file not found at {scraped_path}, skipping merge.")
        return

    # Map datacenter name -> index in centers list
    name_to_idx = {c.get("name"): i for i, c in enumerate(centers)}

    # Heuristic mapping from keywords to datacenter names
    center_keywords = {
        "Greenidge": ["greenidge", "dresden"],
        "Lake Mariner": ["lake mariner", "somerset", "terawulf"],
        "H5 Datacenters": ["h5 datacenters", "h5 data", "h5"],
        "Blockfusion (Niagara Falls)": ["blockfusion", "niagara falls"],
    }

    # Build sets of existing statements per center to avoid duplicates
    existing = {}
    for center in centers:
        name = center.get("name")
        stmts = set()
        for t in center.get("testimonies", []):
            s = t.get("statement", "").strip()
            if s:
                stmts.add(s)
        existing[name] = stmts

    added = 0
    for t in scraped:
        statement = (t.get("statement") or "").strip()
        source = (t.get("source") or "").strip()
        if not statement:
            continue
        text = (statement + " " + source).lower()

        target_name = None
        for center_name, kws in center_keywords.items():
            if any(kw in text for kw in kws):
                target_name = center_name
                break
        if not target_name or target_name not in name_to_idx:
            continue

        if statement in existing.get(target_name, set()):
            continue

        idx = name_to_idx[target_name]
        centers[idx].setdefault("testimonies", []).append(t)
        existing[target_name].add(statement)
        added += 1

    if added:
        with open(centers_path, "w", encoding="utf-8") as f:
            json.dump(centers, f, indent=2, ensure_ascii=False)
    print(f"[merge] Added {added} new testimonies into {centers_path}")


if __name__ == "__main__":
    testimonies = run_scraper()
    # Optionally merge into centers.json so the map picks up new testimonies
    merge_into_centers()
    data = pd.DataFrame(testimonies)
    if not data.empty:
        print("\n--- Preview (DataFrame) ---")
        print(data[["statement", "date", "source-details"]].head(10).to_string())
