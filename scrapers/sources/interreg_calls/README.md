# Interreg

Implementation: bounded discovery of links on official websites; robots.txt respected.

Run from repository root:

```bash
python scrapers/sources/interreg_calls/scraper.py
```

Output: `data/interreg_calls_matches.json` with `profile`, `count`, `scraped_at`, and `matches`. Every match follows the existing scraper-to-web fields; fields unknown from a listing are `null` rather than fabricated.

**Limitations:** This collector is an initial adapter. HTML mode discovers candidate links, not fully validated active calls. Validate status, dates and amounts against source pages before publishing them as confirmed opportunities. CORDIS collects previously funded projects, not necessarily open calls. EU grants mode requires an operator-supplied API search query to avoid conflating grants with tenders.
