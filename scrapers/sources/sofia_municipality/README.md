# Sofia Municipality funding programmes (`sofia_municipality`)

Scrapes funding programmes, calls for proposals and application windows of
**Sofia Municipality (Столична община)** and its funding bodies, and writes them as
normalized records that follow the shared schema in `docs/architecture.md`
(plus a few extra fields, listed below).

## Sources

| key (`--sources`) | Site | What is scraped |
|---|---|---|
| `kultura` | https://kultura.sofia.bg/ | Столична програма „Култура“: application schedule table (“График за кандидатстване”), programme pages (Мобилност, Активни читалища, Млад артист), call announcements from News, and the currently open campaigns on the e-application portal (`/request/public/home/culture2020/index`) |
| `mladite` | https://mladite.sofia.bg/ | Programme „София – град на младите и активните“: programme page, call announcements, open-call portal status |
| `evropa` | https://www.evropa-so.bg/ | Програма „Европа“: one record per priority area (`/bg/nasoki-prioritetna-oblast-N-footer`) with its guidelines, methodology and annex documents from “Кандидатствай тук”, plus call announcements from `/bg/novini` |
| `sofia_bg` | https://www.sofia.bg/ | Programme pages (Социални иновации, Зелена София, детско-юношески спорт/ДЮС, Фонд за младите таланти, Спортна столица) + discovery through the portal’s own search (`/bg/search?q=…&modified=past-year`), filtered to funding-related pages |
| `investsofia` | https://investsofia.com/ (WordPress REST API `/wp-json/wp/v2`) | Accelerator Startup Sofia page and the “Възможности за финансиране” posts (digests) |
| `ogf` | https://ogf-sofia.com/ (WordPress REST API) | Municipal Guarantee Fund for SMEs: FISP start-up guarantee programme and the Basic Guarantee Scheme |

All sources are public, server-rendered HTML or WordPress JSON; no JavaScript rendering or login is needed.
robots.txt was checked for every host (none disallows these paths) and is re-checked at run time.

## How to run

```bash
cd scrapers/sources/sofia_municipality
pip install -r requirements.txt
python scraper.py                                  # all sources (~2–3 min, polite delay)
python scraper.py --sources kultura evropa         # subset
python scraper.py --delay 2 --max-sofia-pages 40 --output-dir /tmp/out -v
```

Polite crawling: custom User-Agent, ≥1.5 s between requests to the same host (`--delay`),
4 retries with exponential back-off on 429/5xx, 30 s timeout, robots.txt respected, UTF-8 forced for Bulgarian text.

## Output

Follows `docs/scraper-to-web-contract.md` (same shape as `eu_funding_tenders`):

- `data/sofia_municipality_matches.json` – `{"profile", "scraped_at", "count", "matches": [...]}`
- `data/sofia_municipality_matches.csv` – flattened, UTF-8 with BOM (Excel), `documents` joined with ` | `

Both are git-ignored (`data/*.json`, `data/*_matches.csv`); run the scraper to regenerate. The web app
(`web/app.py`, `web/app/api/opportunities/route.ts`) merges every `data/*_matches.json`, so Sofia records
appear next to the EU ones automatically.

`match_score` / `matched_keywords` use the shared profile `scrapers/sources/eu_funding_tenders/company_profile.json`
(override with `--profile`, filter with `--min-score`, default 0 = keep all). English keywords are also matched by
Bulgarian equivalents (e.g. `digital` → `дигитал`/`цифров`).

## Record fields (inside `matches`)

Contract fields: `id` (`sofia_municipality:<site>:<sha1[:16]>`), `call_identifier` (always null), `title`, `summary`,
`url`, `status` (`open`/`closed`/`upcoming`/`unknown`), `start_date` (opening date or publication date, ISO),
`deadline` (`YYYY-MM-DD` or null), `source` (always `"sofia_municipality"`), `scraped_at`, `match_score`, `matched_keywords`.

Extras: `description`, `program`, `budget` `{amount, currency}`, `countries` (`["BG"]`), `site` (e.g. `kultura.sofia.bg`),
`region`, `record_type` (`programme`, `programme_strand`, `call_window`, `call_announcement`, `open_call`,
`standing_instrument`, `funding_digest`), `funder`, `target_beneficiaries`, `funding_amount`
`{raw, min, max, currency, total_budget, total_budget_currency}`, `opens_at`, `deadline_raw` (source sentence),
`language`, `documents`, `published_at`.

## Known limitations

- Deadlines and amounts are extracted with Bulgarian-text heuristics; always check `deadline.raw` / `funding_amount.raw`. Dates without a year take the year of the page/publication.
- sofia.bg (Liferay) has no programme index or public JSON API for guests; discovery uses the site search (noisy) + a curated seed list, capped by `--max-sofia-pages`. Some programmes may be missed and an announcement and its programme page may both appear.
- kultura.sofia.bg schedule rows carry dates only (no amounts); the culture programme’s scope pages are PDFs/images and are not parsed. PDF attachments are linked, not read.
- Invest Sofia currently has no open own funding call; its “Възможности за финансиране” posts (2022–2023) are digests of third-party opportunities and are stored with `status: unknown` and no parsed deadline/amount. Only Bulgarian pages are scraped.
- OGF guarantee schemes are standing instruments (no deadline); pages were last updated 2019–2020.
- The mladite.sofia.bg and kultura.sofia.bg application portals list only *currently active* campaigns.
- Opening-only sentences (“На 1 септември стартира приемът…”) now go to `opens_at` instead of `deadline`, and legal references (“Решение № … от 11.12.2008”) are ignored; Invest Sofia’s accelerator no longer reports the guarantee fund’s 31 000 000 BGN portfolio as its budget. These fixes take effect on the next full scraper run. Verify against `deadline_raw` / `funding_amount.raw`.
