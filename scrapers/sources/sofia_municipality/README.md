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

Written to the repo-level `data/` folder (per `scrapers/README.md`):

- `data/sofia_programs.json` – list of records (UTF-8, `ensure_ascii=False`)
- `data/sofia_programs.csv` – flattened, UTF-8 with BOM (opens correctly in Excel); `documents` joined with ` | `

`data/*.json` is git-ignored, so run the scraper to regenerate the data.

## Record fields

| field | meaning |
|---|---|
| `id` | stable id `source:sha1(source|url|name)[:16]` |
| `source`, `source_url` | site key and page the record came from |
| `program_name` | programme / call name (Bulgarian as published) |
| `record_type` | `programme`, `programme_strand`, `call_window`, `call_announcement`, `open_call`, `standing_instrument`, `funding_digest` |
| `description` | first ~700 chars of the page text |
| `funder` | e.g. Столична община, Дирекция „Култура“, Програма „Европа“, Invest Sofia, ОГФ МСП |
| `target_beneficiaries` | eligible applicants paragraph, when found |
| `funding_amount` | `{raw, min, max, currency, total_budget, total_budget_currency}` – `raw` is the source sentence(s); numbers parsed from “до 12 782 евро”, “5 000 – 10 000 лв.”, etc. Currency `EUR` or `BGN` |
| `deadline` | `{date, opens, raw}` – ISO dates when parseable, `raw` = source sentence |
| `status` | `open` / `closed` / `upcoming` / `unknown` (computed from dates vs. run date, or from the portal listing) |
| `language` | `bg` / `en` |
| `documents` | attachment URLs (PDF/DOC/ZIP, Liferay `/documents/d/…`, Axter `service-download-file.php`) |
| `published_at`, `scraped_at` | ISO date / UTC timestamp |
| `title`, `url`, `budget`, `countries`, `region` | aliases matching `docs/architecture.md` |

Example (shape of a real record, shortened):

```json
{
  "id": "sofia.bg:…",
  "source": "sofia.bg",
  "source_url": "https://www.sofia.bg/bg/web/guest/w/7249919",
  "program_name": "До 6 април се приемат кандидатури по Програмата „Социални иновации“ 2026 …",
  "record_type": "call_announcement",
  "funder": "Столична община (Sofia Municipality)",
  "target_beneficiaries": "Могат да кандидатстват юридически лица с нестопанска цел и народни читалища …",
  "funding_amount": {"raw": "През 2026 г. по Програмата ще се финансират проекти на стойност до 12 782 евро всеки, а общият бюджет е до 209 629 евро.",
                     "min": null, "max": 12782.0, "currency": "EUR", "total_budget": 209629.0, "total_budget_currency": "EUR"},
  "deadline": {"date": "2026-04-06", "opens": null, "raw": "До 6 април 2026 г. включително е отворено кандидатстването …"},
  "status": "closed",
  "language": "bg",
  "documents": ["https://www.sofia.bg/documents/d/guest/2026-03-20-programa-socialni-inovacii-2026"],
  "countries": ["BG"],
  "scraped_at": "2026-10-30T13:58:00Z"
}
```

## Known limitations

- Deadlines and amounts are extracted with Bulgarian-text heuristics; always check `deadline.raw` / `funding_amount.raw`. Dates without a year take the year of the page/publication.
- sofia.bg (Liferay) has no programme index or public JSON API for guests; discovery uses the site search (noisy) + a curated seed list, capped by `--max-sofia-pages`. Some programmes may be missed and an announcement and its programme page may both appear.
- kultura.sofia.bg schedule rows carry dates only (no amounts); the culture programme’s scope pages are PDFs/images and are not parsed. PDF attachments are linked, not read.
- Invest Sofia currently has no open own funding call; its “Възможности за финансиране” posts (2022–2023) are digests of third-party opportunities and are stored with `status: unknown` and no parsed deadline/amount. Only Bulgarian pages are scraped.
- OGF guarantee schemes are standing instruments (no deadline); pages were last updated 2019–2020.
- The mladite.sofia.bg and kultura.sofia.bg application portals list only *currently active* campaigns.
- Observed parse errors in the test run (2026-10-30): when a page only states an *opening* date (e.g. “На 1 септември стартира приемът…”), that date can land in `deadline.date`; Invest Sofia’s accelerator page gets a wrong `total_budget` (31 000 000 BGN is the guarantee fund’s historical portfolio, not the accelerator budget). Verify against `raw` before relying on the numbers.
