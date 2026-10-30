# Architecture: European Funding Workflow

## Overview

This repository hosts two main parts that work together:

1. **Scrapers** — Collect funding opportunity data from EU websites.
2. **Web application** — Consumes the scraped data and visualizes it for users.

Other Grok bots can independently push changes into `scrapers/` or `web/`.

## High-level layout

```
/
├── scrapers/          # All scraping code and outputs
├── web/               # Frontend + backend that consume the data
├── docs/              # Architecture, schemas, decisions
└── data/              # Shared JSON outputs from scrapers
```

## Scrapers

- Each EU funding source lives under `scrapers/sources/<source_name>/`.
- Shared helpers (session management, retries, logging, schema validation) live in `scrapers/common/`.
- Preferred output format: structured JSON following a common schema (see below).
- Scrapers should be runnable independently and idempotent where possible.
- Outputs are written to `data/` (e.g. `data/eu_funding_tenders_matches.json`).

### Suggested JSON schema for a funding opportunity

```json
{
  "id": "unique-id",
  "title": "Call title",
  "source": "source_name",
  "url": "https://...",
  "description": "...",
  "program": "Horizon Europe / ERDF / ...",
  "deadline": "2026-12-31",
  "budget": { "amount": 1000000, "currency": "EUR" },
  "countries": ["EU", "BG", "DE"],
  "status": "open",
  "scraped_at": "2026-10-30T12:00:00Z",
  "match_score": 0.42,
  "matched_keywords": ["software", "AI"]
}
```

**See `docs/scraper-to-web-contract.md` for the exact current contract and consumption rules.**

## Web application

- Lives in `web/`.
- Backend loads the latest scraper outputs from `data/*.json`.
- Frontend provides:
  - Searchable / filterable table of opportunities
  - Deadline calendars or timelines
  - Charts (budget by program, geographic distribution, etc.)
  - Detail views linking back to the original source
- Recommended stack (flexible): Next.js or React + a lightweight API (FastAPI / Express).

## Collaboration rules for Grok bots

- Prefer small, focused PRs.
- Scrapers should not depend on web code, and vice versa (shared only via the data schema).
- Document new sources in `scrapers/README.md`.
- Keep secrets out of the repo (use environment variables or GitHub secrets).
- **Agents working on the web app must follow `docs/scraper-to-web-contract.md`.**

## Next steps

1. Implement the first real scraper under `scrapers/sources/` (done for EU Funding & Tenders).
2. Define and lock the funding opportunity schema (see contract doc).
3. Scaffold the web app so it can load and display the JSON from `data/`.
