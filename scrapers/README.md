# Scrapers

This folder contains all code that scrapes EU funding websites.

## Structure

```
scrapers/
├── common/          # Shared utilities
├── sources/         # One subdirectory per funding source
└── requirements.txt
```

## Conventions

- Each source should be independently runnable.
- Output JSON that matches the schema in `docs/architecture.md`.
- Use clear logging and handle rate limits / errors gracefully.
- Prefer `requests` + `BeautifulSoup` / `lxml` or Scrapy for larger sites.

## Adding a new source

1. Create `sources/<source_name>/`.
2. Implement the scraper so it writes valid funding-opportunity JSON.
3. Document the source and any special notes here.

## Output location

Scrapers may write results to `../data/` or expose them via a simple local interface for the web app.
