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

## Available sources

- `sources/sofia_municipality/` — Sofia Municipality funding programmes (sofia.bg, kultura.sofia.bg, mladite.sofia.bg, evropa-so.bg, investsofia.com, ogf-sofia.com). Run `python scraper.py`; writes `data/sofia_programs.json` + `.csv`. Consume the JSON list directly: each record has the `docs/architecture.md` fields (`id`, `title`, `url`, `deadline`, `status`, `budget`, `countries`) plus `funding_amount`, `deadline.raw`, `documents`. See its README.

## Output location

Scrapers may write results to `../data/` or expose them via a simple local interface for the web app.
