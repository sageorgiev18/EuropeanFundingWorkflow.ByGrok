# European Funding Workflow

Website and scrapers for discovering and visualizing EU funding opportunities.

## Architecture

```
scrapers/     → structured JSON data → web/ (visualization)
```

- **scrapers/** — Independent scrapers for different EU funding websites.
- **web/** — Web application that loads the data and provides search, filters, and charts.
- **docs/architecture.md** — Full architecture and data schema.
- **data/** — Optional shared location for scraper outputs.

## Collaboration

Grok bots (and humans) can push to `scrapers/` or `web/` independently as long as they respect the shared funding-opportunity schema.

See `docs/architecture.md` for details.

## Repository

https://github.com/sageorgiev18/EuropeanFundingWorkflow.ByGrok
