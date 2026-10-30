# Scraper → Web Application Contract

This document is for other agents (and developers) working on the `web/` part of the repository.

## Overview

Scrapers produce structured JSON. The web application consumes that JSON to display, filter, and alert on funding opportunities.

```
scrapers/  ──writes──▶  data/*.json  ──reads──▶  web/
```

## Current scraper output

The EU Funding & Tenders scraper writes to:

```
data/eu_funding_tenders_matches.json
```

### Top-level shape

```json
{
  "profile": "Your Company",
  "scraped_at": "2026-10-30T13:00:00+00:00",
  "count": 12,
  "matches": [ /* array of opportunities */ ]
}
```

### Opportunity object (inside `matches`)

| Field              | Type    | Description                                      |
|--------------------|---------|--------------------------------------------------|
| `id`               | string  | Unique identifier from the portal                |
| `call_identifier`  | string  | Human-readable call ID (e.g. `EC-JRC/...`)       |
| `title`            | string  | Title of the call                                |
| `summary`          | string  | Short description / summary                      |
| `url`              | string  | Direct link to the opportunity on the portal     |
| `status`           | string  | Internal status code                             |
| `start_date`       | string  | Publication / start date (ISO)                   |
| `deadline`         | string  | Deadline (YYYY-MM-DD) or null                    |
| `source`           | string  | Always `"eu_funding_tenders"` for this scraper    |
| `scraped_at`       | string  | When this record was scraped                     |
| `match_score`      | number  | Relevance score (0–1) against company profile   |
| `matched_keywords` | string[]| Keywords from the profile that matched           |

## How the web app should consume it

### Recommended approaches (in order of preference)

1. **File-based (simplest for now)**
   - The backend reads `data/eu_funding_tenders_matches.json` (or a configured path).
   - Reload on a schedule or when the file changes.
   - Serve the `matches` array via a REST endpoint, e.g. `GET /api/opportunities`.

2. **Shared volume / object storage**
   - In deployment, mount `data/` or upload the JSON to S3/GCS and let the web app fetch it.

3. **Database (later)**
   - A future improvement: scrapers upsert into a DB; the web app queries the DB.
   - Until then, the JSON file is the source of truth.

### Suggested API surface for the frontend

```
GET /api/opportunities
  ?min_score=0.2
  &deadline_after=2026-11-01
  &q=artificial+intelligence

Response:
{
  "count": 5,
  "opportunities": [ ... ]
}
```

### Alerting

The web app (or a separate notifier) can:
- Compare the current `matches` with the previous run.
- Send alerts (email, Slack, in-app) for new high-scoring opportunities.
- Store `id` + `scraped_at` to avoid duplicate alerts.

## Rules for agents working on scrapers

- Always write valid JSON matching the opportunity shape above.
- Use the `source` field to identify which scraper produced the record.
- Prefer writing to `data/<source>_matches.json`.
- Include `match_score` and `matched_keywords` when relevance filtering is done by the scraper.
- Do not depend on web-app code; the only shared contract is this JSON shape (and the schema in `docs/architecture.md`).

## Rules for agents working on the web app

- Treat `data/*.json` as the input source.
- Be resilient to missing optional fields.
- Do not modify files inside `scrapers/`.
- Display the `url` so users can open the original portal page.
- Show `match_score` and `matched_keywords` so users understand why an opportunity was surfaced.

## Future multi-source support

When more scrapers are added, they should each write their own file under `data/`:

```
data/
  eu_funding_tenders_matches.json
  another_source_matches.json
```

The web app can merge them (or expose per-source endpoints) using the common opportunity shape.
