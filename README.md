# Datacenter Testimonies Map

A research project mapping **resident testimonies** about crypto mining and data center facilities in New York State. The map shows facility locations (Greenidge, Lake Mariner, H5 Datacenters, Blockfusion) and links to reported impacts such as noise, air quality, and health effects.

## Project structure

| File | Description |
|------|-------------|
| `centers.json` | Datacenter data: name, coordinates, county, testimonies (statement, date, source) |
| `datacenters.ipynb` | Jupyter notebook: loads `centers.json` and builds the interactive map |
| `yahoo_news_scraper.py` | Scraper: searches Yahoo News by keywords, extracts testimonies, merges into `centers.json` |

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
