# Datacenter Testimonies Map

A research project mapping **resident testimonies** about crypto mining and data center facilities in New York State. The map shows facility locations (Greenidge, Lake Mariner, H5 Datacenters, Blockfusion) and links to reported impacts such as noise, air quality, and health effects.

## Project structure

| File | Description |
|------|-------------|
| `centers.json` | Datacenter data: name, coordinates, county, testimonies (statement, date, source) |
| `datacenters.ipynb` | Jupyter notebook: loads `centers.json` and builds the interactive map |
| `yahoo_news_scraper.py` | Scraper: searches Yahoo News by keywords, extracts testimonies, merges into `centers.json` |
| `server.py` | Flask app: serves the website and API for testimonies + map data |
| `web/` | React front-end (Vite): map, testimonies list (with search), and “Add testimony” form |

## Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/mikkoliivak/CS4999-Research-SP26
   cd CS4999-Research-SP26
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Running the map

1. Start Jupyter: `jupyter notebook`
2. Open `datacenters.ipynb` and run all cells.
3. The notebook saves the map as `datacenter_testimonies_map.html` (open in a browser).

## Scraping new testimonies

The scraper uses **Selenium** (Chrome in headless mode) and **BeautifulSoup** to search Yahoo News and extract datacenter-related testimonies. New testimonies are merged into `centers.json` automatically.

**Requirements:** Chrome browser installed.

```bash
python yahoo_news_scraper.py
```

Edit `KEYWORDS` at the top of the script to change search terms. Output is merged into `centers.json`; re-run the notebook to refresh the map.

## Requirements

- Python 3.8+
- Chrome (for the scraper)
- See `requirements.txt` for Python packages.

## Website (view testimonies & map, add your own)

A **React** web app lets you **browse testimonies**, **view the map**, and **submit new testimonies** to the bank.

### Production (Flask serves built React app)

1. Activate your venv (e.g. `venv\Scripts\activate` on Windows, `source venv/bin/activate` on macOS/Linux). On Windows PowerShell, if scripts are disabled, use **cmd** and run `venv\Scripts\activate.bat`, or run `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process` once in that terminal, then activate.
2. Install Flask (in your venv): `pip install flask`
3. Build the front-end: `cd web && npm install && npm run build && cd ..`
4. From the project root, run: `python server.py`
5. Open **http://127.0.0.1:5000** in your browser.

### Development (React dev server with hot reload)

1. Activate your venv, then start the API: `python server.py` (leave it running on port 5000).
2. In another terminal (no venv needed): `cd web && npm install && npm run dev`
3. Open **http://127.0.0.1:5173** in your browser. The Vite dev server proxies `/api` to Flask.

**Features:**
- **Map** — Interactive map of NY datacenter locations; click a marker to see testimony count and jump to the list.
- **Testimonies** — Search by keyword (client-side) and filter by facility. Good for finding sound-related quotes.
- **Add testimony** — Form to submit a new quote or statement (facility, statement, date, source). Submissions are stored in `user_testimonies.json` and merged when loading the map/list.

Keyword search is entirely client-side so you can refine results (e.g. for sound-related content) without changing the scraper.
