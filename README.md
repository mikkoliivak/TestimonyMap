# Data Center Noise Testimonies Map

A research project mapping **resident testimonies** about noise from crypto mining and data center facilities across the US. Users can browse an interactive map, search testimonies, and submit new ones via a bookmarklet or web form.

## Project structure

```
├── centers.json           # 645 US data centers (name, coords, testimonies)
├── scraper.py             # News scraper: Bing RSS → fetch → filter → save
├── server.py              # Flask API: serves website + testimony endpoints
├── bookmarklet.js         # Browser bookmarklet for submitting testimonies
├── bookmarklet_url.txt    # Minified bookmarklet URL (paste into bookmark bar)
├── requirements.txt       # Python dependencies
└── web/                   # React frontend (Vite)
    ├── src/               # Components, pages, styles
    ├── index.html
    ├── package.json
    └── vite.config.js
```

## Setup

```bash
git clone https://github.com/mikkoliivak/CS4999-Research-SP26
cd CS4999-Research-SP26
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the website

**Production** (Flask serves built React app):
```bash
cd web && npm install && npm run build && cd ..
python server.py
# Open http://127.0.0.1:5001
```

**Development** (hot reload):
```bash
python server.py                          # Terminal 1: API on :5001
cd web && npm install && npm run dev      # Terminal 2: Vite on :5173
```

## Scraping testimonies

The scraper searches Bing News RSS for articles about data center noise, extracts relevant passages, and merges them into `centers.json`.

```bash
python scraper.py
```

**How it works:**
1. Generates queries: `FACILITIES × IMPACT_TERMS` (e.g. "greenidge noise complaint")
2. Searches Bing News RSS (direct URLs, no API key needed)
3. Fetches articles in parallel (8 threads)
4. Filters passages that contain both a noise term and a topic term
5. Saves to `scraped_testimonies.json`, then merges into `centers.json`

Noise vocabulary is grounded in EPA Noise Control Act (42 U.S.C. §4901), WHO Environmental Noise Guidelines (2018), and ANSI S1.1.

To add a new facility, add an entry to `FACILITIES` in `scraper.py`.

## Bookmarklet

The bookmarklet lets you highlight text on any news article, click the bookmark, and submit it as a testimony to a specific data center.

1. Copy the contents of `bookmarklet_url.txt`
2. Create a new bookmark in your browser and paste it as the URL
3. On any article, highlight relevant text and click the bookmark

## Data sources

- **Data centers**: OpenStreetMap Overpass API (645 US facilities)
- **News articles**: Bing News RSS
- **User testimonies**: Submitted via bookmarklet or web form

## Requirements

- Python 3.8+
- Node.js (for building the frontend)
- See `requirements.txt` for Python packages
