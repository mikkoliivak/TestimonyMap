# Datacenter Testimonies Map

A research project mapping **resident testimonies** about crypto mining and data center facilities in New York State. The map shows facility locations (e.g., Greenidge, Lake Mariner, H5 Datacenters, Blockfusion) and links to reported impacts such as noise, air quality, and health effects, with sources and dates.

## Project structure

| File | Description |
|------|-------------|
| `datacenters.ipynb` | Jupyter notebook that builds the interactive map from the datacenter dataset |
| `datacenter_testimonies_map.html` | Output map: open in a browser to explore locations and testimonies |
| `centers.json` | Datacenter data (name, coordinates, county, testimonies with statement, date, source) |

## Setup

1. **Clone the repo** (if you haven’t already):
   ```bash
   git clone <repo-url>
   cd "CS4999 Research SP26"
   ```

2. **Create and use a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the notebook

1. Start Jupyter:
   ```bash
   jupyter notebook
   ```
2. Open `datacenters.ipynb` and run all cells (Cell → Run All).
3. The last cell saves the map as `datacenter_testimonies_map.html`.

To view the map without re-running the notebook, open `datacenter_testimonies_map.html` in a web browser.

## Requirements

- Python 3.8+
- See `requirements.txt` for Python packages (`folium`, `jupyter`, `notebook`).

## Data

Testimonies are collected from cited news and advocacy sources (e.g., Earthjustice, Ithaca Week, Digital Journal). Each testimony includes the statement, date, and source link. The map uses marker color to reflect the number of testimonies per site (gray: none, orange: 1–4, red: 5+).
