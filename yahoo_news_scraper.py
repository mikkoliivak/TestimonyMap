from bs4 import BeautifulSoup
from urllib.parse import quote_plus, parse_qs, unquote
from urllib.parse import urlparse
import re
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import pandas as pd
import requests

try:
    import trafilatura  # type: ignore
except Exception:
    trafilatura = None

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

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
WAIT_FOR_RESULTS_SEC = 5


def now_iso_utc():
    return datetime.now(timezone.utc).isoformat()


def resolve_yahoo_redirect(url):
    """
    Yahoo search sometimes returns redirect URLs like:
    https://r.search.yahoo.com/.../RU=<encoded_target>/RK=...
    """
    try:
        if not url:
            return url
        if "r.search.yahoo.com" not in url:
            return url
        qs = parse_qs(urlparse(url).query)
        if "RU" in qs and qs["RU"]:
            return unquote(qs["RU"][0])
        m = re.search(r"/RU=([^/]+)/", url)
        if m:
            return unquote(m.group(1))
        return url
    except Exception:
        return url


def normalize_url(href):
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    href = resolve_yahoo_redirect(href)
    return href


def parse_yahoo_pub_meta(text):
    """
    Parse strings like: 'Reuters · Aug 21, 2024' or 'Associated Press · 2 days ago'
    Returns (publisher, pubdate_raw).
    """
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if "·" not in text:
        return "", ""
    left, right = [t.strip() for t in text.split("·", 1)]
    if len(left) > 60 or len(right) > 60:
        return "", ""
    if left.lower() in {"share", "save", "sign in", "log in"}:
        return "", ""
    return left, right


def parse_yahoo_search_results(html, max_items=10):
    """
    Parse Yahoo News search results into structured items:
      link, title, pubdate_raw, description, publisher
    """
    bs = BeautifulSoup(html or "", "html.parser")

    containers = []
    for sel in [
        "div.NewsArticle", "li.NewsArticle",
        "div.algo", "li.algo",
        "ol.searchCenterMiddle > li",
        "div#web ol > li",
        "div#results ol > li",
    ]:
        found = bs.select(sel)
        if found:
            containers.extend(found)

    if not containers:
        # Fallback: scan a bounded number of blocks and look for headline-like links
        containers = bs.find_all(["article", "li", "div"], limit=300)

    items = []
    seen_links = set()
    for c in containers:
        a = c.select_one("h4 a[href], h3 a[href], a[href]")
        if not a:
            continue

        href = normalize_url(a.get("href"))
        if not href or not href.startswith("http"):
            continue
        if "search.yahoo.com" in href or "news.search.yahoo.com" in href or "login." in href:
            continue

        title = a.get_text(" ", strip=True) or ""
        if len(title) < 8:
            continue

        if href in seen_links:
            continue
        seen_links.add(href)

        description = ""
        desc_el = c.select_one("p, div.compText p")
        if desc_el:
            description = desc_el.get_text(" ", strip=True) or ""

        publisher = ""
        pubdate_raw = ""
        meta_texts = []
        for el in c.select("span, div"):
            t = el.get_text(" ", strip=True)
            if "·" in t and 5 <= len(t) <= 120:
                meta_texts.append(t)
        for t in meta_texts:
            pub, dt = parse_yahoo_pub_meta(t)
            if pub or dt:
                publisher, pubdate_raw = pub, dt
                break

        items.append(
            {
                "link": href,
                "title": title,
                "pubdate_raw": pubdate_raw,
                "description": description,
                "publisher": publisher,
            }
        )
        if len(items) >= max_items:
            break

    return items


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
        # Set a hard page-load timeout so individual articles can't hang forever.
        driver.set_page_load_timeout(20)
        return driver
    except Exception as e:
        print("Selenium: could not start Chrome. Install Chrome and try again:", e)
        raise


def search_yahoo_news(driver, keyword):
    """Load Yahoo News search with Selenium, then parse page source with BeautifulSoup."""
    query = quote_plus(keyword)
    url = "https://news.search.yahoo.com/search?p={}&ei=UTF-8".format(query)
    try:
        driver.get(url)
        # Wait for results to appear, then parse result blocks.
        WebDriverWait(driver, WAIT_FOR_RESULTS_SEC).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href]"))
        )
        time.sleep(1)
        html = driver.page_source
    except Exception as e:
        print("  [skip] Yahoo search failed:", e)
        return []

    return parse_yahoo_search_results(html, max_items=MAX_ARTICLES_PER_QUERY)


REQUESTS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
}


def search_google_news_rss(keyword, max_items=10):
    """Fetch Google News RSS feed for a keyword. No Selenium needed."""
    query = quote_plus(keyword)
    url = "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en".format(query)
    try:
        resp = requests.get(url, timeout=15, headers=REQUESTS_HEADERS)
        resp.raise_for_status()
    except Exception as e:
        print("  [skip] Google News RSS failed: {}".format(e))
        return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        print("  [skip] Google News RSS XML parse error: {}".format(e))
        return []

    items = []
    for item in root.iter("item"):
        if len(items) >= max_items:
            break
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        publisher = (source_el.text or "").strip() if source_el is not None else ""
        description = (item.findtext("description") or "").strip()

        if not link or not link.startswith("http"):
            continue

        # Parse RFC 2822 date from RSS
        pubdate_raw = ""
        if pub_date:
            try:
                dt = parsedate_to_datetime(pub_date)
                pubdate_raw = dt.strftime("%b %d, %Y")
            except Exception:
                pubdate_raw = pub_date

        # Strip HTML from description
        if description:
            description = BeautifulSoup(description, "html.parser").get_text(" ", strip=True)

        items.append({
            "link": link,
            "title": title,
            "pubdate_raw": pubdate_raw,
            "description": description,
            "publisher": publisher,
        })

    return items


def resolve_google_news_url(driver, url):
    """
    Resolve a Google News redirect URL (https://news.google.com/rss/articles/...)
    to the actual article URL by following the JS redirect in Selenium.
    Returns the resolved URL, or the original URL if resolution fails.
    """
    if "news.google.com" not in url:
        return url
    try:
        # Temporarily increase timeout for the redirect page
        driver.set_page_load_timeout(30)
        try:
            driver.get(url)
        except TimeoutException:
            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass
        # Give the JS redirect a moment
        time.sleep(2)
        final = driver.current_url or url
        # Restore original timeout
        driver.set_page_load_timeout(20)
        if final and "news.google.com" not in final and final.startswith("http"):
            return final
    except Exception as e:
        print("    [skip] Could not resolve Google News URL:", e)
        try:
            driver.set_page_load_timeout(20)
        except Exception:
            pass
    return url


def fetch_article_lightweight(url):
    """
    Fetch article HTML with requests (no Selenium).
    Returns (final_url, html) or None on failure.
    """
    try:
        resp = requests.get(
            url, timeout=15, headers=REQUESTS_HEADERS, allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.url, resp.text
    except Exception:
        return None


def normalize_date(pubdate_str):
    if not pubdate_str:
        return ""
    pubdate_str = pubdate_str.strip()
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", pubdate_str)
    if m:
        a, b, c = m.groups()
        if len(c) == 2:
            c = "20" + c
        return "{}-{}-{}".format(a, b, c)
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(pubdate_str, fmt)
            return "{}-{}-{}".format(dt.month, dt.day, dt.year)
        except Exception:
            pass
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


def extract_publisher_from_html(html, url=""):
    """
    Best-effort publisher extraction from article HTML.
    Tries JSON-LD NewsArticle.publisher.name and common meta tags.
    """
    try:
        bs = BeautifulSoup(html or "", "html.parser")

        for s in bs.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
            raw = (s.string or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            candidates = data if isinstance(data, list) else [data]
            for obj in candidates:
                if not isinstance(obj, dict):
                    continue
                typ = obj.get("@type") or obj.get("type")
                if isinstance(typ, list):
                    typ = " ".join(str(x) for x in typ)
                if typ and "NewsArticle" not in str(typ) and "Article" not in str(typ):
                    continue
                pub = obj.get("publisher") or {}
                if isinstance(pub, dict):
                    name = (pub.get("name") or "").strip()
                    if name:
                        return name
                if isinstance(pub, list):
                    for p in pub:
                        if isinstance(p, dict):
                            name = (p.get("name") or "").strip()
                            if name:
                                return name

        for sel in [
            'meta[name="publisher"]',
            'meta[property="og:site_name"]',
            'meta[name="application-name"]',
            'meta[name="parsely-site"]',
        ]:
            t = bs.select_one(sel)
            if t and (t.get("content") or "").strip():
                return t.get("content").strip()
    except Exception:
        pass
    return source_name(url) if url else ""


def extract_title_from_html(html):
    try:
        bs = BeautifulSoup(html or "", "html.parser")
        og = bs.select_one('meta[property="og:title"]')
        if og and (og.get("content") or "").strip():
            return og.get("content").strip()
        if bs.title and bs.title.get_text(strip=True):
            return bs.title.get_text(" ", strip=True)
    except Exception:
        pass
    return ""


def extract_published_from_html(html):
    try:
        bs = BeautifulSoup(html or "", "html.parser")
        t = bs.select_one(
            'meta[property="article:published_time"], meta[name="pubdate"], meta[name="date"]'
        )
        if t and (t.get("content") or "").strip():
            return t.get("content").strip()

        for s in bs.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
            raw = (s.string or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            candidates = data if isinstance(data, list) else [data]
            for obj in candidates:
                if isinstance(obj, dict) and (obj.get("datePublished") or "").strip():
                    return obj.get("datePublished").strip()
    except Exception:
        pass
    return ""


def extract_main_text(html, url=""):
    """
    Extract "main article text" to reduce nav/footer boilerplate.
    Uses trafilatura if available; falls back to cleaned BeautifulSoup text.
    """
    if trafilatura is not None:
        try:
            extracted = trafilatura.extract(
                html or "",
                url=url or None,
                include_comments=False,
                include_tables=False,
                include_links=False,
                favor_recall=True,
            )
            if extracted:
                return re.sub(r"\s+", " ", extracted).strip()
        except Exception:
            pass

    try:
        bs = BeautifulSoup(html or "", "html.parser")
        for tag in bs(["script", "style", "noscript"]):
            tag.decompose()
        for tag in bs.find_all(["header", "footer", "nav", "aside"]):
            tag.decompose()
        text = bs.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


def split_sentences(text):
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def get_context(sentences, idx, before=1, after=1):
    start = max(0, idx - before)
    end = min(len(sentences), idx + after + 1)
    return " ".join(sentences[start:end]).strip()


def fetch_article_html(driver, url):
    """Fetch an article with Selenium and return (final_url, html)."""
    try:
        driver.get(url)
    except TimeoutException:
        # Stop loading and use whatever content we have so far, or skip if empty.
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass
    time.sleep(1)
    try:
        final_url = driver.current_url or url
    except Exception:
        final_url = url
    html = driver.page_source
    return final_url, html


def extract_quotes_from_article(
    url,
    driver=None,
    rss_description="",
    result_title="",
    result_publisher="",
    result_pubdate_raw="",
    search_keyword="",
):
    """
    Fetch article and extract sound-related quotes + context.

    Tries a lightweight requests fetch first (less detectable).
    Falls back to Selenium only if the lightweight fetch fails or
    returns too little text (JS-heavy page).

    Returns:
      testimonies: list of {statement, extraction_method}
      meta: dict with publisher/title/published + url info
    """
    sound_pat = re.compile(
        r"\b(" + "|".join(re.escape(w) for w in SOUND_WORDS) + r")\b", re.I
    )
    topic_pat = re.compile(
        r"(" + "|".join(re.escape(w) for w in TOPIC_WORDS) + r")", re.I
    )
    testimonies = []

    # --- Try lightweight fetch first (requests, no Selenium) ---
    html = None
    final_url = url
    result = fetch_article_lightweight(url)
    if result:
        final_url, html = result
        # If the extracted text is too short, the page likely needs JS rendering
        quick_text = extract_main_text(html, url=final_url)
        if len(quick_text) < 200:
            html = None

    # --- Fall back to Selenium if lightweight fetch failed ---
    if html is None and driver is not None:
        try:
            final_url, html = fetch_article_html(driver, url)
        except Exception as e:
            print("    [skip] Could not fetch:", e)
            return [], {}

    if html is None:
        print("    [skip] Could not fetch (no driver available)")
        return [], {}

    publisher_html = extract_publisher_from_html(html, final_url)
    title_html = extract_title_from_html(html)
    published_html_raw = extract_published_from_html(html)

    publisher_final = (result_publisher or "").strip() or (publisher_html or "").strip() or source_name(final_url)
    title_final = (result_title or "").strip() or (title_html or "").strip()
    published_norm = normalize_date(published_html_raw) or normalize_date(result_pubdate_raw)

    meta = {
        "url_requested": url,
        "url_final": final_url,
        "publisher_result": (result_publisher or "").strip(),
        "pubdate_result_raw": (result_pubdate_raw or "").strip(),
        "title_result": (result_title or "").strip(),
        "search_keyword": (search_keyword or "").strip(),
        "publisher_html": (publisher_html or "").strip(),
        "published_html_raw": (published_html_raw or "").strip(),
        "title_html": (title_html or "").strip(),
        "publisher_final": publisher_final,
        "published_norm": published_norm,
        "title_final": title_final,
    }

    main_text = extract_main_text(html, url=final_url)
    sentences = split_sentences(main_text)
    seen = set()

    def add(block, method):
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
        testimonies.append({"statement": block, "extraction_method": method})

    for i, sent in enumerate(sentences):
        if not sound_pat.search(sent):
            continue
        add(get_context(sentences, i, before=SENTENCES_BEFORE, after=SENTENCES_AFTER), "sentence_context")

    for m in re.finditer(r'"([^"]{20,600})"', main_text):
        quoted = m.group(1).strip()
        for i, sent in enumerate(sentences):
            if quoted[:20] in sent or quoted[-20:] in sent:
                add(get_context(sentences, i, before=SENTENCES_BEFORE, after=SENTENCES_AFTER), "inline_quote_context")
                break
        else:
            add(quoted, "inline_quote")

    try:
        bs = BeautifulSoup(html, "html.parser")
        for bq in bs.find_all("blockquote"):
            t = bq.get_text(separator=" ", strip=True)
            if 30 < len(t) < 1500:
                add(t, "blockquote")
    except Exception:
        pass

    if rss_description and 30 < len(rss_description) < 800:
        if sound_pat.search(rss_description) or "said" in rss_description.lower():
            add(rss_description, "result_snippet")

    return testimonies, meta


def _process_search_results(items, search_keyword, search_source, driver, all_testimonies, seen):
    """Process a list of search result items from any source."""
    for art in items:
        link = art["link"]
        # Resolve Google News redirect URLs to actual article URLs
        if "news.google.com" in link and driver is not None:
            resolved = resolve_google_news_url(driver, link)
            if resolved != link:
                print("    Resolved: {} -> {}".format(link[:60], resolved[:80]))
                link = resolved
                art["link"] = link
        result_title = art.get("title", "")
        result_publisher = art.get("publisher", "")
        result_pubdate_raw = art.get("pubdate_raw", "")
        result_snippet = art.get("description", "")

        quotes, meta = extract_quotes_from_article(
            link,
            driver=driver,
            rss_description=result_snippet,
            result_title=result_title,
            result_publisher=result_publisher,
            result_pubdate_raw=result_pubdate_raw,
            search_keyword=search_keyword,
        )

        pub = meta.get("published_norm") or normalize_date(result_pubdate_raw)
        publisher_final = meta.get("publisher_final") or (result_publisher or "").strip() or source_name(link)
        title_final = meta.get("title_final") or (result_title or "").strip()
        url_final = meta.get("url_final") or link

        for q in quotes:
            st = (q.get("statement") or "").strip()
            if not st or len(st) < 25:
                continue
            key = st[:200]
            if key in seen:
                continue
            seen.add(key)
            all_testimonies.append({
                "statement": st,
                "date": pub or "Unknown",
                "source": url_final,
                "source-details": publisher_final,

                # Extra metadata (keeps map-compatible keys above)
                "publisher": publisher_final,
                "article_title": title_final,
                "search_keyword": search_keyword,
                "search_source": search_source,
                "retrieved_at": now_iso_utc(),
                "extraction_method": (q.get("extraction_method") or ""),
                "result_snippet": result_snippet,
                "result_publisher": result_publisher,
                "result_pubdate_raw": result_pubdate_raw,
                "url_requested": meta.get("url_requested") or link,
            })
        time.sleep(DELAY_SECONDS)


def run_scraper(save_path="scraped_testimonies.json"):
    driver = None
    try:
        driver = get_driver()
        all_testimonies = []
        seen = set()

        # --- Google News RSS (no Selenium needed for search) ---
        for kw in KEYWORDS:
            print("Searching Google News RSS: '{}'".format(kw))
            items = search_google_news_rss(kw, max_items=MAX_ARTICLES_PER_QUERY)
            print("  Found {} articles".format(len(items)))
            _process_search_results(items, kw, "google_news_rss", driver, all_testimonies, seen)
            time.sleep(DELAY_SECONDS)

        # --- Yahoo News (Selenium search) ---
        for kw in KEYWORDS:
            print("Searching Yahoo News: '{}'".format(kw))
            items = search_yahoo_news(driver, kw)
            print("  Found {} articles".format(len(items)))
            _process_search_results(items, kw, "yahoo_news", driver, all_testimonies, seen)
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

    # Build lists of existing statements per center to check near-duplicates
    existing = {}
    for center in centers:
        name = center.get("name")
        stmts = []
        for t in center.get("testimonies", []):
            s = t.get("statement", "").strip()
            if s:
                stmts.append(s)
        existing[name] = stmts

    def _is_near_duplicate(new_stmt, existing_stmts):
        """Check if new_stmt is a near-duplicate of any existing statement."""
        for ex in existing_stmts:
            if new_stmt in ex or ex in new_stmt:
                return True
            if len(new_stmt) > 50 and len(ex) > 50 and new_stmt[:100] == ex[:100]:
                return True
        return False

    # Clean 'Advertisement' filler from incoming statements
    adv_pat = re.compile(r"\bAdvertisement\b")

    added = 0
    for t in scraped:
        statement = (t.get("statement") or "").strip()
        statement = re.sub(r"\s+", " ", adv_pat.sub("", statement)).strip()
        t["statement"] = statement
        source = (t.get("source") or "").strip()
        if not statement or len(statement) < 30:
            continue
        text = (statement + " " + source).lower()

        target_name = None
        for center_name, kws in center_keywords.items():
            if any(kw in text for kw in kws):
                target_name = center_name
                break
        if not target_name or target_name not in name_to_idx:
            continue

        if _is_near_duplicate(statement, existing.get(target_name, [])):
            continue

        idx = name_to_idx[target_name]
        centers[idx].setdefault("testimonies", []).append(t)
        existing[target_name].append(statement)
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
