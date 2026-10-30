#!/usr/bin/env python3
"""
Sofia Municipality (Столична община) funding programmes scraper.

Collects funding programmes, calls for proposals and application windows from
the official websites of Sofia Municipality and its funding bodies, and writes
normalized records to data/sofia_municipality_matches.json (and a flattened
data/sofia_municipality_matches.csv). The JSON follows docs/scraper-to-web-contract.md:
{"profile", "scraped_at", "count", "matches": [opportunity, ...]} with
source = "sofia_municipality", so the web app picks it up next to the other scrapers.

Sources (all public, server-rendered HTML or WordPress REST JSON):
  * sofia.bg              - municipal portal (Liferay): programme pages + site search discovery
  * kultura.sofia.bg      - Culture Directorate: Столична програма „Култура“, Мобилност,
                            Активни читалища, Млад артист, application schedule, open-call portal
  * mladite.sofia.bg      - youth programme „София – град на младите и активните“
  * evropa-so.bg          - Програма „Европа“ (5 priority areas, calls, documents)
  * investsofia.com       - Invest Sofia (WordPress REST API): Accelerator Startup Sofia,
                            "Възможности за финансиране" posts
  * ogf-sofia.com         - Municipal Guarantee Fund for SMEs (WordPress REST API)

Usage:
    python scraper.py                      # all sources
    python scraper.py --sources kultura evropa --delay 2
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import logging
import os
import re
import sys
import time
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlencode
from urllib import robotparser

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("sofia_scraper")

USER_AGENT = (
    "Mozilla/5.0 (compatible; EuropeanFundingWorkflow-SofiaScraper/1.0; "
    "+https://github.com/sageorgiev18/EuropeanFundingWorkflow.ByGrok)"
)
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.normpath(os.path.join(HERE, "..", "..", "..", "data"))  # repo-level data/ per scrapers/README.md
SOURCE_ID = "sofia_municipality"  # contract: `source` identifies the scraper
OUTPUT_BASENAME = f"{SOURCE_ID}_matches"  # contract: data/<source>_matches.json
DEFAULT_PROFILE = os.path.normpath(os.path.join(HERE, "..", "eu_funding_tenders", "company_profile.json"))
TODAY = dt.date.today()

FUNDER_SO = "Столична община (Sofia Municipality)"
FUNDER_CULTURE = "Столична община – Дирекция „Култура“ (Sofia Municipality, Culture Directorate)"
FUNDER_YOUTH = "Столична община – Дирекция „Спорт и младежки дейности“ (Sofia Municipality)"
FUNDER_EUROPE = "Столична община – Програма „Европа“ (Sofia Municipality, Europe Programme)"
FUNDER_IS = "Инвест София / СОАПИ (Invest Sofia, Sofia Municipal Agency for Privatization and Investment)"
FUNDER_OGF = "Общински гаранционен фонд за МСП към Столична община (Municipal Guarantee Fund for SMEs)"

DOC_EXT = re.compile(r"\.(pdf|docx?|xlsx?|odt|ods|zip|rar|7z|pptx?)(\?|$)", re.I)
DOC_HINTS = ("/documents/d/", "service-download-file.php", "/media/attachments/",
             "/wp-content/uploads/", "/web/guest/d/")


# --------------------------------------------------------------------------- HTTP
class PoliteSession:
    """requests.Session with retries, per-host delay and robots.txt checks."""

    def __init__(self, delay: float = 1.5, timeout: int = 30):
        self.delay = delay
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "bg,en;q=0.8",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        })
        retry = Retry(total=4, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET", "HEAD"), respect_retry_after_header=True)
        adapter = HTTPAdapter(max_retries=retry)
        self.s.mount("https://", adapter)
        self.s.mount("http://", adapter)
        self._last: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self.blocked: list[str] = []
        self.errors: list[str] = []

    def _robots_ok(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                r = self.s.get(base + "/robots.txt", timeout=self.timeout)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[base] = rp
        rp = self._robots[base]
        return rp.can_fetch(USER_AGENT, url) if rp else True

    def get(self, url: str, **kw) -> requests.Response | None:
        if not self._robots_ok(url):
            log.warning("robots.txt disallows %s - skipped", url)
            self.blocked.append(url)
            return None
        host = urlparse(url).netloc
        wait = self.delay - (time.time() - self._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        try:
            r = self.s.get(url, timeout=self.timeout, **kw)
        except requests.RequestException as e:
            log.error("GET %s failed: %s", url, e)
            self.errors.append(f"{url}: {e}")
            return None
        finally:
            self._last[host] = time.time()
        if r.status_code != 200:
            log.warning("GET %s -> HTTP %s", url, r.status_code)
            self.errors.append(f"{url}: HTTP {r.status_code}")
            return None
        # Force correct decoding of Bulgarian text.
        if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
            r.encoding = "utf-8"
        return r

    def soup(self, url: str, **kw) -> BeautifulSoup | None:
        r = self.get(url, **kw)
        return BeautifulSoup(r.text, "lxml") if r is not None else None

    def json(self, url: str, **kw):
        r = self.get(url, **kw)
        if r is None:
            return None
        try:
            return r.json()
        except ValueError:
            log.error("Invalid JSON from %s", url)
            return None


# --------------------------------------------------------------------------- text helpers
WS = re.compile(r"[ \t\u00a0\u200b\u200c\u200d\ufeff]+")


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = text.replace("\r", "\n")
    text = WS.sub(" ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return "\n".join(line.strip() for line in text.split("\n") if line.strip()).strip()


def strip_shortcodes(html: str) -> str:
    return re.sub(r"\[/?[a-z_]+[^\]]*\]", " ", html or "")


def sentences(text: str) -> list[str]:
    flat = re.sub(r"\s*\n\s*", " ", text)
    parts = re.split(r"(?<=[.!?;])\s+(?=[А-ЯA-Z„\"(0-9●•])|\s+[●•►]\s*", flat)
    return [p.strip() for p in parts if p and p.strip()]


def language_of(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "und"
    cyr = sum(1 for c in letters if "\u0400" <= c <= "\u04ff")
    return "bg" if cyr / len(letters) > 0.3 else "en"


def shorten(text: str, n: int = 700) -> str:
    text = re.sub(r"\s*\n\s*", " ", text or "").strip()
    return text if len(text) <= n else text[: n].rsplit(" ", 1)[0] + " …"


# --------------------------------------------------------------------------- dates
MONTHS = {
    "януари": 1, "февруари": 2, "март": 3, "април": 4, "май": 5, "юни": 6, "юли": 7,
    "август": 8, "септември": 9, "октомври": 10, "ноември": 11, "декември": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE_NUM = re.compile(r"(?<!\d)(\d{1,2})\s?[./]\s?(\d{1,2})\s?[./]\s?(\d{4})(?!\d)")
DATE_TXT = re.compile(rf"(?<!\d)(\d{{1,2}})(?:-?(?:ви|ри|ти|ми))?\s+({MONTH_RE})\s*(\d{{4}})?", re.I)
# "от 1 до 31 март 2026"  -> two dates sharing month/year
DATE_SPAN = re.compile(rf"от\s+(\d{{1,2}})\s+до\s+(\d{{1,2}})\s+({MONTH_RE})\s*(\d{{4}})?", re.I)
DEADLINE_KW = re.compile(r"кандидатств|прием|приемат|подава|подават|подаване|краен срок|срок за|срокът|"
                         r"отворен|отваря|набиране|applications?|deadline|submit", re.I)
NOT_DEADLINE_KW = re.compile(r"изпълнени|реализаци|отчет|оценяване|класиране|заседание|договор", re.I)
# words that mark a date as the *start* of an application window
OPEN_KW = re.compile(r"стартира|започва|открива|откриваме|отваря|отворена за кандидатстване от|"
                     r"\bот\s+(?:\d|00:)|opens?\b|starts?\b|from\b", re.I)
# words that mark a date as the *end* of an application window
CLOSE_KW = re.compile(r"\bдо\s+(?:\d|23:|00:)|краен срок|крайният срок|срокът|не по-късно|deadline|until|by\s+\d", re.I)
# "Решение № 759 от 11.12.2008 г." / "Заповед № СОА24-РД09-3266/11.07.2024 г." are legal references, not deadlines
LEGAL_REF = re.compile(r"(?:Решение|Заповед|Протокол)\s*№\s*[\w\-/.]+(?:\s*от\s*\d{1,2}\.\d{1,2}\.\d{4}\s*г?\.?)?", re.I)


def _mk(d: int, m: int, y: int | None, default_year: int | None) -> dt.date | None:
    y = y or default_year
    if not y:
        return None
    try:
        return dt.date(int(y), int(m), int(d))
    except ValueError:
        return None


def find_dates(s: str, default_year: int | None = None) -> list[tuple[int, dt.date]]:
    out: list[tuple[int, dt.date]] = []
    taken: list[tuple[int, int]] = []
    years_in = [int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", s)]
    dy = years_in[0] if years_in else default_year
    for m in DATE_SPAN.finditer(s):
        y = int(m.group(4)) if m.group(4) else dy
        mon = MONTHS[m.group(3).lower()]
        for g in (1, 2):
            d = _mk(int(m.group(g)), mon, y, dy)
            if d:
                out.append((m.start(g), d))
        taken.append(m.span())
    for m in DATE_NUM.finditer(s):
        if any(a <= m.start() < b for a, b in taken):
            continue
        d = _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)), dy)
        if d:
            out.append((m.start(), d))
            taken.append(m.span())
    for m in DATE_TXT.finditer(s):
        if any(a <= m.start() < b for a, b in taken):
            continue
        y = int(m.group(3)) if m.group(3) else None
        d = _mk(int(m.group(1)), MONTHS[m.group(2).lower()], y, dy)
        if d:
            out.append((m.start(), d))
    out.sort(key=lambda x: x[0])
    return out


def extract_deadline(text: str, default_year: int | None = None) -> dict:
    """Return {'date': ISO|None, 'opens': ISO|None, 'raw': sentence|None}."""
    best = None
    for sent in sentences(text):
        if not DEADLINE_KW.search(sent):
            continue
        dates = find_dates(LEGAL_REF.sub(" ", sent), default_year)
        if not dates:
            continue
        score = 2
        if re.search(r"кандидатств|прием|приемат|подава|deadline|applications?", sent, re.I):
            score += 2
        if CLOSE_KW.search(sent):
            score += 1  # an explicit end date beats a start-only announcement
        elif len(dates) == 1 and OPEN_KW.search(sent):
            score -= 1
        if NOT_DEADLINE_KW.search(sent) and score < 4:
            score -= 2
        if best is None or score > best[0]:
            best = (score, sent, dates)
        if score >= 5:
            break
    if not best or best[0] <= 0:
        return {"date": None, "opens": None, "raw": None}
    _, sent, dates = best
    opens = None
    ds = [d for _, d in dates]
    if len(ds) >= 2 and re.search(r"\bот\b|from|between|[–-]|период", sent, re.I):
        opens, deadline = ds[0], max(ds)
        if deadline <= opens:
            opens, deadline = None, ds[0]
    elif len(ds) == 1 and OPEN_KW.search(sent) and not CLOSE_KW.search(sent):
        # "На 1 септември стартира приемът ..." -> opening date only, no deadline known
        return {"date": None, "opens": ds[0].isoformat(), "raw": shorten(sent, 400)}
    else:
        deadline = ds[0]
    return {"date": deadline.isoformat(), "opens": opens.isoformat() if opens else None,
            "raw": shorten(sent, 400)}


# --------------------------------------------------------------------------- amounts
NUM = r"(\d{1,3}(?:[ \u00a0.]\d{3})+|\d+)(?:,(\d{1,2}))?"
CUR = r"(евро|eur|€|лв\.?|лева|bgn)"
MULT = r"(хил\.?|хиляди|млн\.?|милиона?)?"
AMOUNT = re.compile(rf"{NUM}\s*{MULT}\s*{CUR}", re.I)
RANGE = re.compile(rf"{NUM}\s*{MULT}\s*(?:{CUR})?\s*(?:–|—|-|до)\s*{NUM}\s*{MULT}\s*{CUR}", re.I)
PER_PROJECT = re.compile(r"максимал|на проект|за проект|един проект|отделен проект|всеки|единична|"
                         r"индивидуален проект|per project|grant|до\s+\d", re.I)
TOTAL = re.compile(r"общ(ия|ият)? (бюджет|размер)|бюджет(ът)? на програмата|общо|total budget|финансова рамка", re.I)


def _num(intpart: str, dec: str | None, mult: str | None) -> float:
    v = float(re.sub(r"[ \u00a0.]", "", intpart) + ("." + dec if dec else ""))
    if mult:
        m = mult.lower()
        v *= 1000 if m.startswith("хил") else 1_000_000
    return v


def _cur(c: str) -> str:
    c = c.lower()
    return "EUR" if c in ("евро", "eur", "€") else "BGN"


def extract_amount(text: str) -> dict:
    res = {"raw": None, "min": None, "max": None, "currency": None, "total_budget": None,
           "total_budget_currency": None}
    raws: list[str] = []
    for sent in sentences(text):
        if not AMOUNT.search(sent):
            continue
        # ignore per-person net pay lines / bank-guarantee portfolio stats when nothing else
        rng = RANGE.search(sent)
        if rng and res["max"] is None:
            lo = _num(rng.group(1), rng.group(2), rng.group(3))
            hi = _num(rng.group(5), rng.group(6), rng.group(7))
            cur = _cur(rng.group(8))
            if lo < hi:
                res.update(min=lo, max=hi, currency=cur)
                raws.append(sent)
                continue
        amts = [(m, _num(m.group(1), m.group(2), m.group(3)), _cur(m.group(4))) for m in AMOUNT.finditer(sent)]
        if TOTAL.search(sent) and res["total_budget"] is None:
            # largest number in a "total budget" sentence is the programme budget
            m, v, c = max(amts, key=lambda x: x[1])
            res.update(total_budget=v, total_budget_currency=c)
            raws.append(sent)
            if PER_PROJECT.search(sent) and res["max"] is None and len(amts) > 1:
                m2, v2, c2 = min(amts, key=lambda x: x[1])
                res.update(max=v2, currency=c2)
            continue
        if res["max"] is None and PER_PROJECT.search(sent):
            m, v, c = amts[0]
            res.update(max=v, currency=c)
            raws.append(sent)
            continue
        if len(raws) < 3:
            raws.append(sent)
    if raws:
        res["raw"] = shorten(" | ".join(dict.fromkeys(raws)), 500)
    return res


# --------------------------------------------------------------------------- beneficiaries / status
BENEF_KW = re.compile(r"(допустими (кандидати|бенефициенти)|бенефициенти|могат да кандидатстват|"
                      r"право да кандидатстват|кандидатстват|target group|eligible|целева (група|аудитория)|"
                      r"насочен[аи]? към|изисквания към)", re.I)


def extract_beneficiaries(text: str) -> str | None:
    lines = [l for l in text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        m = BENEF_KW.search(line)
        if not m:
            continue
        if re.search(r"недопустим", line, re.I):
            continue
        chunk = line[m.start():]
        j = i + 1
        while len(chunk) < 350 and j < len(lines) and not re.search(r"недопустим", lines[j], re.I):
            chunk += " " + lines[j]
            j += 1
        return shorten(chunk, 450)
    return None


def compute_status(deadline: dict, text: str = "", force: str | None = None) -> str:
    if force:
        return force
    d = deadline.get("date")
    o = deadline.get("opens")
    if d:
        dd = dt.date.fromisoformat(d)
        if o and TODAY < dt.date.fromisoformat(o):
            return "upcoming"
        return "open" if TODAY <= dd else "closed"
    if o and TODAY < dt.date.fromisoformat(o):
        return "upcoming"
    if re.search(r"затворена за кандидатстване|приключи(ла)? приемът", text, re.I):
        return "closed"
    return "unknown"


def collect_documents(container, base_url: str) -> list[str]:
    docs: list[str] = []
    if container is None:
        return docs
    for a in container.find_all("a", href=True):
        h = a["href"].strip()
        if h.startswith(("mailto:", "tel:", "javascript:", "#", "file:")):
            continue
        absu = urljoin(base_url, h)
        if DOC_EXT.search(absu) or any(k in absu for k in DOC_HINTS):
            absu = absu.split("&p_l_back_url")[0].split("?p_l_back_url")[0]
            if absu not in docs:
                docs.append(absu)
    return docs


def make_record(*, source: str, source_url: str, program_name: str, text: str, funder: str,
                documents: list[str] | None = None, record_type: str = "programme",
                published_at: str | None = None, deadline: dict | None = None,
                amount: dict | None = None, status: str | None = None,
                beneficiaries: str | None = None, description: str | None = None,
                default_year: int | None = None) -> dict:
    text = clean(text)
    if deadline is None:
        deadline = extract_deadline(text, default_year)
    if amount is None:
        amount = extract_amount(text)
    # `source` here is the site key (e.g. "kultura.sofia.bg"); the record's contract `source` is SOURCE_ID
    site = source
    rid = hashlib.sha1(f"{site}|{source_url}|{program_name}".encode("utf-8")).hexdigest()[:16]
    desc = description if description is not None else shorten(text, 700)
    name = clean(program_name)
    amount = amount or {}
    rec = {
        # --- fields from docs/scraper-to-web-contract.md (same order as eu_funding_tenders) ---
        "id": f"{SOURCE_ID}:{site}:{rid}",
        "call_identifier": None,  # municipal calls carry no official call ID
        "title": name,
        "summary": shorten(desc, 400),
        "url": source_url,
        "status": compute_status(deadline, text, status),  # open / closed / upcoming / unknown
        "start_date": deadline.get("opens") or published_at,
        "deadline": deadline.get("date"),  # YYYY-MM-DD or null
        "source": SOURCE_ID,
        "scraped_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "match_score": 0.0,  # filled in by score_records()
        "matched_keywords": [],
        # --- docs/architecture.md extras ---
        "description": desc,
        "program": name,
        "budget": ({"amount": amount.get("max") or amount.get("total_budget"),
                    "currency": amount.get("currency") or amount.get("total_budget_currency")}
                   if (amount.get("max") or amount.get("total_budget")) else None),
        "countries": ["BG"],
        # --- Sofia-specific extras ---
        "site": site,
        "region": "Sofia (Столична община)",
        "record_type": record_type,
        "funder": funder,
        "target_beneficiaries": beneficiaries if beneficiaries is not None else extract_beneficiaries(text),
        "funding_amount": amount,
        "opens_at": deadline.get("opens"),
        "deadline_raw": deadline.get("raw"),
        "language": language_of(program_name + " " + text[:2000]),
        "documents": documents or [],
        "published_at": published_at,
    }
    return rec


def year_from(s: str | None) -> int | None:
    m = re.search(r"(20\d{2})", s or "")
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------- source: kultura.sofia.bg (Axter CMS)
def axter_item(http: PoliteSession, url: str):
    """Return (title, published, text, documents, soup) for an Axter CMS page."""
    soup = http.soup(url)
    if soup is None:
        return None
    body = soup.select_one(".new-item-content") or soup.select_one("#main-content")
    if body is None:
        return None
    for t in body(["script", "style"]):
        t.decompose()
    title_el = None
    card = body.find_parent(class_="card-body") or body
    for h in card.find_all(["h1", "h2", "h3", "h4"]):
        if h.get_text(strip=True):
            title_el = h
            break
    title = title_el.get_text(" ", strip=True) if title_el else (soup.title.get_text(strip=True) if soup.title else url)
    txt = clean(body.get_text("\n"))
    pub = None
    m = re.search(r"Дата на публикуване:\s*(\d{2}\.\d{2}\.\d{4})", txt)
    if m:
        d = dt.datetime.strptime(m.group(1), "%d.%m.%Y").date()
        pub = d.isoformat()
        txt = txt.replace(m.group(0), "").strip()
    txt = re.sub(r"^Дата на публикуване:\s*", "", txt).strip()
    return title, pub, txt, collect_documents(body, url), soup


def axter_open_calls(http: PoliteSession, portal_url: str, source: str, funder: str, program_hint: str) -> list[dict]:
    soup = http.soup(portal_url)
    if soup is None:
        return []
    page_text = clean(soup.get_text("\n"))
    if "кампанията не е активна" in page_text:
        log.info("%s: portal says no campaign is active", portal_url)
        return []
    out = []
    for tr in soup.select("table tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        campaign, name = tds[1].get_text(" ", strip=True), tds[2].get_text(" ", strip=True)
        link = tr.find("a", href=True)
        url = urljoin(portal_url, link["href"]) if link else portal_url
        out.append(make_record(
            source=source, source_url=url, program_name=name, funder=funder,
            text=f"{campaign}: {name}. Активна кампания за електронно кандидатстване в портала {portal_url}.",
            record_type="open_call", status="open",
            description=f"Currently listed as an active application campaign on the e-application portal ({campaign}).",
            deadline={"date": None, "opens": None, "raw": "Listed as active on the application portal"},
        ))
    return out


def scrape_kultura(http: PoliteSession) -> list[dict]:
    base = "https://kultura.sofia.bg/"
    src = "kultura.sofia.bg"
    out: list[dict] = []
    home = http.soup(base + "home.html")
    if home is None:
        return out
    links = [(a.get_text(" ", strip=True), urljoin(base, a["href"])) for a in home.find_all("a", href=True)]

    # 1) Application schedule table ("График за кандидатстване YYYY")
    sched = [(t, u) for t, u in links if t.startswith("График за кандидатстване")]
    sched.sort(key=lambda x: year_from(x[0]) or 0, reverse=True)
    if sched:
        t, u = sched[0]
        soup = http.soup(u)
        table = soup.select_one("table.schedule-table, .new-item-content table") if soup else None
        if table:
            caption = table.caption.get_text(" ", strip=True) if table.caption else t
            for tr in table.select("tbody tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
                if len(cells) < 3 or not cells[0]:
                    continue
                name, start, end = cells[0], cells[1], cells[2]
                ds = find_dates(start)
                de = find_dates(end)
                deadline = {"date": de[0][1].isoformat() if de else None,
                            "opens": ds[0][1].isoformat() if ds else None,
                            "raw": f"{start} – {end}"}
                out.append(make_record(
                    source=src, source_url=u, program_name=name, funder=FUNDER_CULTURE,
                    text=f"{caption}. {name}: от {start} до {end}.",
                    record_type="call_window", deadline=deadline,
                    amount={"raw": None, "min": None, "max": None, "currency": None,
                            "total_budget": None, "total_budget_currency": None},
                    beneficiaries=None,
                    description=f"Application window from the Culture Directorate schedule '{caption}': "
                                f"{name}, applications {start} – {end}.",
                ))

    # 2) Programme pages (Мобилност, Активни читалища, Млад артист, ...)
    prog = []
    for t, u in links:
        if re.match(r"^Програма\s*[„\"“]", t) and re.search(r"section-\d+-content\.html$", u) and u not in [p[1] for p in prog]:
            prog.append((t, u))
    for t, u in prog:
        item = axter_item(http, u)
        if not item:
            continue
        title, pub, txt, docs, _ = item
        out.append(make_record(source=src, source_url=u, program_name=t, text=txt, funder=FUNDER_CULTURE,
                               documents=docs, record_type="programme", published_at=pub,
                               default_year=year_from(pub)))

    # 3) News announcing calls ("прием", "стартира", "кандидатстване")
    news = http.soup(base + "section-9-text.html")
    if news:
        seen = set()
        for a in news.find_all("a", href=True):
            t = a.get_text(" ", strip=True)
            u = urljoin(base, a["href"])
            if "currentNews" not in u or u in seen or not t:
                continue
            seen.add(u)
            if not re.search(r"прием|стартира|кандидатств|отваря", t, re.I) or re.search(r"^Списък", t):
                continue
            item = axter_item(http, u)
            if not item:
                continue
            title, pub, txt, docs, _ = item
            out.append(make_record(source=src, source_url=u, program_name=t, text=txt, funder=FUNDER_CULTURE,
                                   documents=docs, record_type="call_announcement", published_at=pub,
                                   default_year=year_from(pub)))

    # 4) Currently open campaigns on the e-application portal
    out += axter_open_calls(http, "https://kultura.sofia.bg/request/public/home/culture2020/index",
                            src, FUNDER_CULTURE, "Столична програма „Култура“")
    return out


# --------------------------------------------------------------------------- source: mladite.sofia.bg
def scrape_mladite(http: PoliteSession) -> list[dict]:
    base = "https://mladite.sofia.bg/"
    src = "mladite.sofia.bg"
    out: list[dict] = []
    item = axter_item(http, base + "section-5-content.html")
    if item:
        title, pub, txt, docs, _ = item
        out.append(make_record(source=src, source_url=base + "section-5-content.html",
                               program_name="Програма „София – град на младите и активните“",
                               text=txt, funder=FUNDER_YOUTH, documents=docs, published_at=pub,
                               default_year=year_from(pub)))
    news = http.soup(base + "section-1-text.html")
    if news:
        seen = set()
        for a in news.find_all("a", href=True):
            t = a.get_text(" ", strip=True)
            u = urljoin(base, a["href"])
            if "currentNews" not in u or u in seen or not t:
                continue
            seen.add(u)
            if t.startswith("Проект") or not re.search(r"програма|прием|сесия|кандидатств", t, re.I):
                continue
            it = axter_item(http, u)
            if not it:
                continue
            title, pub, txt, docs, _ = it
            out.append(make_record(source=src, source_url=u, program_name=t, text=txt, funder=FUNDER_YOUTH,
                                   documents=docs, record_type="call_announcement", published_at=pub,
                                   default_year=year_from(pub) or year_from(t)))
    out += axter_open_calls(http, base + "request/public/home/sofia-young/index", src, FUNDER_YOUTH,
                            "София – град на младите и активните")
    return out


# --------------------------------------------------------------------------- source: evropa-so.bg (Joomla)
def joomla_article(http: PoliteSession, url: str):
    soup = http.soup(url)
    if soup is None:
        return None
    art = soup.select_one("article.item-page") or soup.select_one("[itemprop=articleBody]")
    if art is None:
        return None
    for t in art(["script", "style"]):
        t.decompose()
    h = art.find(["h1", "h2"])
    title = h.get_text(" ", strip=True) if h else (soup.title.get_text(strip=True) if soup.title else url)
    pub = None
    meta = soup.find("meta", attrs={"property": "article:published_time"}) or art.find("time")
    if meta is not None:
        pub = (meta.get("content") or meta.get("datetime") or "")[:10] or None
    return title, pub, clean(art.get_text("\n")), collect_documents(art, url), art


def scrape_evropa(http: PoliteSession) -> list[dict]:
    base = "https://www.evropa-so.bg"
    src = "evropa-so.bg"
    out: list[dict] = []
    # Documents per priority area from "Кандидатствай тук"
    area_docs: dict[int, list[str]] = {}
    general_docs: list[str] = []
    k = joomla_article(http, base + "/bg/kandidatstvai-tuk")
    if k:
        art = k[4]
        current = None
        for el in art.descendants:
            if getattr(el, "name", None) is None:
                m = re.search(r"Приоритетна област\s*(\d)", str(el), re.I)
                if m:
                    current = int(m.group(1))
                continue
            if el.name == "a" and el.get("href"):
                u = urljoin(base + "/", el["href"])
                if not (DOC_EXT.search(u) or any(h in u for h in DOC_HINTS)):
                    continue
                (area_docs.setdefault(current, []) if current else general_docs).append(u)
    # Programme parameters from the latest call announcement (applies to all areas)
    news = http.soup(base + "/bg/novini")
    call_text, call_url, call_pub = "", None, None
    if news:
        seen = []
        for a in news.find_all("a", href=True):
            t = a.get_text(" ", strip=True)
            u = urljoin(base + "/", a["href"])
            if "/novini/" in u and t and t != "Прочети още …" and u not in [s[1] for s in seen]:
                seen.append((t, u))
        for t, u in seen:
            if not re.search(r"отвар|отворена|прием|покана за кандидатстване", t, re.I):
                continue
            art = joomla_article(http, u)
            if not art:
                continue
            title, pub, txt, docs, _ = art
            yr = year_from(t) or year_from(pub)
            rec = make_record(source=src, source_url=u, program_name=t, text=txt, funder=FUNDER_EUROPE,
                              documents=docs, record_type="call_announcement", published_at=pub,
                              default_year=yr)
            out.append(rec)
            if not call_text:
                call_text, call_url, call_pub = txt, u, pub
    # One record per priority area (guidelines pages linked from the footer)
    for n in range(1, 10):
        u = f"{base}/bg/nasoki-prioritetna-oblast-{n}-footer"
        art = joomla_article(http, u)
        if not art:
            break
        title, pub, txt, docs, _ = art
        m = re.search(r"Приоритетна област\s*%d\s*:?\s*\n?(.+)" % n, txt, re.I)
        area = clean(m.group(1)).split("\n")[0] if m else ""
        yr_m = re.search(r"ПРОГРАМА „ЕВРОПА“\s*(20\d{2})", txt)
        yr = yr_m.group(1) if yr_m else ""
        name = f"Програма „Европа“ {yr} – Приоритетна област {n}: {area}".strip(" :")
        # deadline/amount: from the guidelines themselves, falling back to the call announcement
        # the call announcement states the real application window; the guidelines cite old council decisions
        dl = extract_deadline(call_text, int(yr) if yr else None) if call_text else {"date": None}
        if not dl.get("date"):
            dl = extract_deadline(txt, int(yr) if yr else None)
        amt = extract_amount(txt)
        if amt["max"] is None and amt["total_budget"] is None and call_text:
            amt = extract_amount(call_text)
        out.append(make_record(source=src, source_url=u, program_name=name, text=txt, funder=FUNDER_EUROPE,
                               documents=area_docs.get(n, []) + general_docs + docs,
                               record_type="programme_strand", deadline=dl, amount=amt,
                               published_at=pub))
    return out


# --------------------------------------------------------------------------- source: sofia.bg (Liferay)
SOFIA = "https://www.sofia.bg"
SOFIA_SEEDS = [
    # (url, follow_links)
    (SOFIA + "/bg/program-social-innovation", False),
    (SOFIA + "/bg/web/guest/program-green-sofia-2024", False),
    (SOFIA + "/bg/web/guest/sessions-dus", False),
    (SOFIA + "/bg/web/guest/sofia-young-talent-fund", True),
    (SOFIA + "/bg/web/guest/appling-for-co-financing", True),
]
SOFIA_QUERIES = [
    "прием на проектни предложения",
    "програма кандидатстване проекти",
    "отворена за кандидатстване",
    "публична покана проектни предложения",
    "сесия за набиране на проектни предложения",
]
TITLE_OK = re.compile(r"програм|прием|кандидат|покана|фонд|сесия|конкурс|мярка|финансир", re.I)
TITLE_BAD = re.compile(r"архив|често задавани|резултат|класиране|списък|одобрен|отчет|договор", re.I)


def _sofia_norm(u: str) -> str:
    u = u.split("?")[0].split("#")[0]
    return u.replace("/bg/web/guest/", "/bg/").rstrip("/")


def _is_sofia_page(u: str) -> bool:
    p = urlparse(u)
    if p.netloc not in ("www.sofia.bg", "sofia.bg"):
        return False
    path = p.path
    if any(x in path for x in ("/d/", "/documents/", "/c/", "/search", "/o/")):
        return False
    return path.startswith("/bg/") or path.startswith("/w/")


def sofia_page(http: PoliteSession, url: str):
    soup = http.soup(url)
    if soup is None:
        return None
    main = soup.select_one("#main-content") or soup.select_one("#content")
    if main is None:
        return None
    for t in main(["script", "style", "nav", "form"]):
        t.decompose()
    title = soup.title.get_text(strip=True) if soup.title else url
    title = re.sub(r"\s*-\s*Портал на Столичната [оО]бщина.*$", "", title).strip()
    pub = None
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        pub = meta["content"][:10]
    return title, pub, clean(main.get_text("\n")), collect_documents(main, url), main


def scrape_sofia_bg(http: PoliteSession, max_pages: int = 40) -> list[dict]:
    src = "sofia.bg"
    out: list[dict] = []
    queue: list[tuple[str, bool, str | None]] = [(u, f, None) for u, f in SOFIA_SEEDS]
    for q in SOFIA_QUERIES:
        url = SOFIA + "/bg/search?" + urlencode({"q": q, "modified": "past-year", "delta": 60})
        soup = http.soup(url)
        if soup is None:
            continue
        for li in soup.select("li.list-group-item"):
            a = li.find("a", href=True)
            if not a:
                continue
            t = a.get_text(" ", strip=True)
            u = urljoin(SOFIA, a["href"])
            if _is_sofia_page(u) and TITLE_OK.search(t) and not TITLE_BAD.search(t):
                queue.append((u.split("?")[0], False, t))
    seen: set[str] = set()
    fetched = 0
    while queue and fetched < max_pages:
        url, follow, hint = queue.pop(0)
        key = _sofia_norm(url)
        if key in seen:
            continue
        seen.add(key)
        page = sofia_page(http, url)
        fetched += 1
        if not page:
            continue
        title, pub, txt, docs, main = page
        if follow:
            for a in main.find_all("a", href=True):
                u = urljoin(SOFIA, a["href"])
                t = a.get_text(" ", strip=True)
                if _is_sofia_page(u) and TITLE_OK.search(t + " " + u) and not re.search(r"архив", t, re.I):
                    queue.insert(0, (u.split("?")[0], False, t))
        if TITLE_BAD.search(title):
            continue
        if not re.search(r"кандидатств|проектни предложения|финансиран", txt, re.I):
            continue
        if follow and len(txt) < 400:
            continue  # pure hub page, children are scraped instead
        out.append(make_record(source=src, source_url=url, program_name=title, text=txt,
                               funder=FUNDER_SO, documents=docs, published_at=pub,
                               record_type="programme" if "/w/" not in url else "call_announcement",
                               default_year=year_from(title) or year_from(pub)))
    return out


# --------------------------------------------------------------------------- WordPress sources
def wp_text(html: str) -> tuple[str, BeautifulSoup]:
    soup = BeautifulSoup(strip_shortcodes(html), "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    return clean(soup.get_text("\n")), soup


def scrape_investsofia(http: PoliteSession) -> list[dict]:
    api = "https://investsofia.com/wp-json/wp/v2"
    src = "investsofia.com"
    out: list[dict] = []
    for slug in ("accelerator-startup-sofia",):
        data = http.json(f"{api}/pages", params={"slug": slug})
        for p in data or []:
            txt, soup = wp_text(p["content"]["rendered"])
            title = BeautifulSoup(p["title"]["rendered"], "lxml").get_text(" ", strip=True)
            amt = extract_amount(txt)
            # the page's only "total" figure is the guarantee fund's historical portfolio, not the
            # accelerator budget -> do not report it as the programme budget
            amt.update(total_budget=None, total_budget_currency=None)
            out.append(make_record(source=src, source_url=p["link"], program_name=title, text=txt, amount=amt,
                                   funder=FUNDER_IS + "; " + FUNDER_OGF + "; " + FUNDER_EUROPE,
                                   documents=collect_documents(soup, p["link"]), record_type="programme",
                                   published_at=p.get("date", "")[:10] or None,
                                   default_year=year_from(p.get("modified"))))
    # Posts tagged "Възможности за финансиране" (funding-opportunity digests)
    cats = http.json(f"{api}/categories", params={"search": "Възможности за финансиране"}) or []
    for c in cats:
        posts = http.json(f"{api}/posts", params={"categories": c["id"], "per_page": 100}) or []
        for p in posts:
            txt, soup = wp_text(p["content"]["rendered"])
            title = BeautifulSoup(p["title"]["rendered"], "lxml").get_text(" ", strip=True)
            date = p.get("date", "")[:10]
            out.append(make_record(
                source=src, source_url=p["link"], program_name=f"{title} ({date})", text=txt,
                funder=FUNDER_IS + " (digest of third-party opportunities)",
                documents=collect_documents(soup, p["link"]), record_type="funding_digest",
                published_at=date or None,
                # digests bundle several unrelated opportunities -> do not guess one deadline/amount
                deadline={"date": None, "opens": None, "raw": None},
                amount={"raw": None, "min": None, "max": None, "currency": None,
                        "total_budget": None, "total_budget_currency": None},
                beneficiaries=None, status="unknown"))
    return out


def scrape_ogf(http: PoliteSession) -> list[dict]:
    api = "https://ogf-sofia.com/wp-json/wp/v2"
    src = "ogf-sofia.com"
    out: list[dict] = []
    for slug in ("programa-za-finansirane-na-inovativni-startirashti-predpriyatiya", "osnovna-garantsionna-shema"):
        data = http.json(f"{api}/pages", params={"slug": slug})
        for p in data or []:
            txt, soup = wp_text(p["content"]["rendered"])
            title = BeautifulSoup(p["title"]["rendered"], "lxml").get_text(" ", strip=True)
            out.append(make_record(source=src, source_url=p["link"], program_name=title, text=txt,
                                   funder=FUNDER_OGF, documents=collect_documents(soup, p["link"]),
                                   record_type="standing_instrument",
                                   published_at=p.get("date", "")[:10] or None,
                                   deadline={"date": None, "opens": None,
                                             "raw": "Standing loan-guarantee scheme, no fixed call deadline published"}))
    return out


# --------------------------------------------------------------------------- relevance scoring
# The shared company profile has English keywords; municipal pages are Bulgarian, so each keyword
# is also matched by its Bulgarian equivalents (stems).
BG_SYNONYMS = {
    "software": ["софтуер"],
    "artificial intelligence": ["изкуствен интелект"],
    "ai": ["изкуствен интелект"],
    "machine learning": ["машинно обучение"],
    "data analytics": ["анализ на данни", "данни"],
    "digital": ["дигитал", "цифров"],
    "it services": ["ит услуги", "информационни технологии", "икт"],
    "cloud": ["облачн"],
    "cybersecurity": ["киберсигурност"],
    "web application": ["уеб приложение", "уебсайт", "онлайн платформ"],
    "automation": ["автоматизац"],
    "innovation": ["иноваци"],
    "startup": ["стартъп", "стартиращ"],
}


def load_profile(path: str | None) -> dict:
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"name": "Sofia Municipality (no profile)", "keywords": []}


def _kw_hit(kw: str, text: str) -> bool:
    terms = [kw.lower()] + BG_SYNONYMS.get(kw.lower(), [])
    for t in terms:
        if len(t) <= 3:  # short tokens like "AI" / "ИКТ" need word boundaries
            if re.search(rf"(?<![\w]){re.escape(t)}(?![\w])", text):
                return True
        elif t in text:
            return True
    return False


def score_records(records: list[dict], profile: dict) -> None:
    """Same formula as eu_funding_tenders.score_match: hits (+0.5 per multi-word phrase) / #keywords."""
    keywords = profile.get("keywords", [])
    for r in records:
        text = re.sub(r"\s+", " ", " ".join(str(r.get(k) or "") for k in
                                            ("title", "description", "target_beneficiaries"))).lower()
        hits = [kw for kw in keywords if _kw_hit(kw, text)]
        bonus = sum(0.5 for kw in hits if " " in kw)
        r["match_score"] = round(min(1.0, (len(hits) + bonus) / max(len(keywords), 1)), 3) if keywords else 0.0
        r["matched_keywords"] = hits


# --------------------------------------------------------------------------- output
CSV_FIELDS = ["id", "site", "url", "title", "record_type", "funder", "status",
              "start_date", "deadline", "deadline_raw", "opens_at", "funding_amount_raw", "funding_min",
              "funding_max", "funding_currency", "total_budget", "total_budget_currency", "target_beneficiaries",
              "summary", "description", "language", "documents", "published_at", "match_score",
              "matched_keywords", "source", "scraped_at"]


def to_row(r: dict) -> dict:
    a = r.get("funding_amount") or {}
    row = {k: r.get(k) for k in CSV_FIELDS}
    row.update({
        "funding_amount_raw": a.get("raw"), "funding_min": a.get("min"), "funding_max": a.get("max"),
        "funding_currency": a.get("currency"), "total_budget": a.get("total_budget"),
        "total_budget_currency": a.get("total_budget_currency"),
        "documents": " | ".join(r.get("documents") or []),
        "matched_keywords": ", ".join(r.get("matched_keywords") or []),
    })
    return row


def write_outputs(records: list[dict], outdir: str, profile_name: str) -> tuple[str, str]:
    os.makedirs(outdir, exist_ok=True)
    jpath = os.path.join(outdir, OUTPUT_BASENAME + ".json")
    cpath = os.path.join(outdir, OUTPUT_BASENAME + ".csv")
    payload = {  # top-level shape from docs/scraper-to-web-contract.md
        "profile": profile_name,
        "scraped_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "count": len(records),
        "matches": records,
    }
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(cpath, "w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel shows Cyrillic
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in records:
            w.writerow(to_row(r))
    return jpath, cpath


SOURCES = {
    "kultura": scrape_kultura,
    "mladite": scrape_mladite,
    "evropa": scrape_evropa,
    "sofia_bg": scrape_sofia_bg,
    "investsofia": scrape_investsofia,
    "ogf": scrape_ogf,
}


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", nargs="+", choices=list(SOURCES), default=list(SOURCES))
    ap.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests to the same host")
    ap.add_argument("--max-sofia-pages", type=int, default=40)
    ap.add_argument("--profile", default=DEFAULT_PROFILE,
                    help="company profile JSON for match_score (default: eu_funding_tenders/company_profile.json)")
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="drop records scoring below this (default 0 = keep all; the dataset is small)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    http = PoliteSession(delay=args.delay)
    records: list[dict] = []
    for name in args.sources:
        log.info("Scraping %s ...", name)
        try:
            fn = SOURCES[name]
            recs = fn(http, args.max_sofia_pages) if name == "sofia_bg" else fn(http)
        except Exception as e:  # keep other sources running
            log.exception("Source %s failed: %s", name, e)
            recs = []
        log.info("  %s: %d records", name, len(recs))
        records.extend(recs)
    # de-duplicate by id
    uniq = list({r["id"]: r for r in records}.values())
    profile = load_profile(args.profile)
    score_records(uniq, profile)
    uniq = [r for r in uniq if r["match_score"] >= args.min_score]
    uniq.sort(key=lambda r: r["match_score"], reverse=True)
    jpath, cpath = write_outputs(uniq, args.output_dir, profile.get("name", "N/A"))
    log.info("Wrote %d records -> %s, %s", len(uniq), jpath, cpath)
    if http.blocked:
        log.warning("Skipped by robots.txt: %d URLs", len(http.blocked))
    if http.errors:
        log.warning("%d request errors (first 5): %s", len(http.errors), http.errors[:5])
    return 0 if uniq else 1


if __name__ == "__main__":
    sys.exit(main())
