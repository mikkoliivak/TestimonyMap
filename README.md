# Data Center Noise Testimonies Map

Map and manage testimonies about noise impacts from U.S. data centers and related facilities.

## Overview

This project includes:
- A React map frontend (`web/`)
- A Flask backend (`server.py`)
- A scraper pipeline (`scraper.py`) that gathers testimony passages from news coverage
- A shared facility dataset (`centers.json`)

## Repository Layout

```text
centers.json
scraper.py
server.py
bookmarklet.js
bookmarklet_url.txt
requirements.txt
web/
```

## Prerequisites

- Python 3.8+
- Node.js 18+ (recommended)

## Setup

```bash
git clone https://github.com/mikkoliivak/CS4999-Research-SP26
cd CS4999-Research-SP26
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd web
npm install
```

## Run Locally

Backend:

```bash
python server.py
```

Frontend (dev mode, separate terminal):

```bash
cd web
npm run dev
```

Frontend (build for Flask static serving):

```bash
cd web
npm run build
```

## Scraper Workflow

Run the scraper and merge results into `centers.json`:

```bash
python scraper.py
```

Outputs:
- `scraped_testimonies.json` (raw extracted passages)
- Updated `centers.json` (merged testimonies)

## Bookmarklet

Use the bookmarklet to submit highlighted article text as testimony:
1. Copy the value from `bookmarklet_url.txt`
2. Create a browser bookmark and paste it as the bookmark URL
3. Highlight relevant text and run the bookmarklet on the article page

## Data Sources

- OpenStreetMap Overpass API (facility metadata)
- Bing News RSS (article discovery)
- User submissions (bookmarklet/API)
