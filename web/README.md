# Web Application (Streamlit)

Simple, open-source dashboard that consumes the scraper JSON and visualizes matching EU funding opportunities.

## Stack

- **Streamlit** — pure Python, easiest to develop, test, and ship.
- Reads `data/eu_funding_tenders_matches.json` (see `docs/scraper-to-web-contract.md`).

## Local development

```bash
cd web
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

- Streamlit Community Cloud (free for public repos)
- Or any Docker host (Dockerfile included)

## Data contract

Follows `docs/scraper-to-web-contract.md`. The app expects the `matches` array from the scraper output.

## Features

- Filter by minimum match score
- Search in title / summary
- Sortable table with portal links
- Expandable details for top matches
