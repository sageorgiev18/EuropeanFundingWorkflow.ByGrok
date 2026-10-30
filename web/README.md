# Web Application

This folder contains the website that consumes scraper output and visualizes EU funding opportunities.

## Suggested structure

```
web/
├── frontend/         # UI (React / Next.js / etc.)
├── backend/          # API that loads and serves funding data
└── package.json       # or equivalent
```

## Responsibilities

- Load the latest structured data produced by the scrapers from `data/*.json`.
- Provide filtering, search, and rich visualizations.
- Link back to the original funding call pages.
- Surface `match_score` and `matched_keywords` so users understand relevance.

## Data contract

**Primary reference:** `docs/scraper-to-web-contract.md`

Also see the schema in `docs/architecture.md`.

The current scraper writes to `data/eu_funding_tenders_matches.json`. The backend should read this file (or a configured path) and expose the `matches` array via an API for the frontend.

## Getting started

Scaffold a Next.js or React + FastAPI project here when ready. The only dependency on the scrapers is the JSON contract documented above.
