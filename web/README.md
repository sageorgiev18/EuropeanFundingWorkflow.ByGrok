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

- Load the latest structured data produced by the scrapers.
- Provide filtering, search, and rich visualizations.
- Link back to the original funding call pages.

## Data contract

The web app expects funding opportunities in the JSON schema defined in `docs/architecture.md`.

## Getting started

Scaffold a Next.js or React + FastAPI project here when ready.
