# EU Funding & Tenders Portal (Calls for Tenders)

Source: https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-tenders

Uses the official public SEDIA Search API:
`POST https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA`

## Usage

```bash
cd scrapers
pip install -r requirements.txt
python -m sources.eu_funding_tenders.scraper
```

Edit `company_profile.json` to match your company (keywords, CPV codes, sectors).

Matching opportunities are written to `data/eu_funding_tenders_matches.json` (relative to repo root).

## Matching

The scraper scores each open/forthcoming call against the company profile using keyword overlap in title, summary, and CPV description. Results above a threshold are kept for alerting / the web app.
