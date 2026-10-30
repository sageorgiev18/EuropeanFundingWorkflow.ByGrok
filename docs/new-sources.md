# Eight additional funding collectors

The modules live under `scrapers/sources/<name>/` with independent `scraper.py` and `README.md` files. Shared HTTP and schema logic lives under `scrapers/common/funding_sources.py`. Existing sources and web app are not changed.

Install from repo root: `pip install -r scrapers/requirements-extra.txt`

Run unit tests: `python -m pytest tests/test_funding_sources.py -q`

- `ted_procurement`: official TED Search API v3. Configure `--ted-query` using current official expert-search syntax.
- `cordis_projects`: official CORDIS CSV exports. Configure `--cordis-csv-url`; projects are historical grants, not open funding calls.
- `eu_grants`: existing SEDIA Search API with `--eu-grants-query` containing a verified JSON search query; do not copy a calls-for-tenders query.
- `isun_bulgaria`, `interreg_calls`, `eufunds_bg`, `innovation_ministry`, `eic_funding`: official-site listing discovery with robots.txt respect, per-host pacing and bounded results. These output candidate links; enrichment of details, statuses, budgets, and application dates remains follow-up work.

All outputs: `data/<source>_matches.json` as `{profile, scraped_at, count, matches}`. Each match includes `id`, `title`, `source`, `url`, `summary`, `deadline`, `status`, `match_score`, `matched_keywords`, `scraped_at` and optional domain-specific fields. Unknown dates/amounts remain null. Existing Next.js route currently reads only `data/eu_funding_tenders_matches.json`: to display all sources add a separate read/merge route with validation and de-duplication before shipping.

**Important:** CORDIS project records and listing links do not imply currently open funding. Consult source terms, robots, and official programme pages before using results as authoritative.
