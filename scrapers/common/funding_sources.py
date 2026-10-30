"""Shared collectors; independent output per source, compatible opportunity fields."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
USER_AGENT = "EuropeanFundingWorkflow/1.0 (public-funding-indexer; contact: configure-your-email)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json,text/csv;q=0.9,*/*;q=0.5"}
KEYWORDS = ("fund", "grant", "call", "tender", "programme", "program", "project", "apply", "proposal", "procedure", "финанс", "процед", "кандидат", "покан", "проект", "програма", "конкурс", "поръчк", "иновац")


def canonical(source, url, title, *, summary="", deadline=None, status="unknown", scraped_at=None, **extra):
    if not url.startswith(("https://", "http://")):
        raise ValueError("URL must be absolute")
    ident = hashlib.sha256(f"{source}|{url}".encode()).hexdigest()[:20]
    record = {"id": f"{source}:{ident}", "call_identifier": None, "title": title.strip()[:500],
              "summary": summary.strip()[:3000], "description": summary.strip()[:3000], "source": source,
              "url": url, "status": status, "start_date": None, "deadline": deadline,
              "scraped_at": scraped_at or datetime.now(timezone.utc).isoformat(),
              "match_score": None, "matched_keywords": [], "budget": None, "countries": []}
    record.update(extra)
    return record


def save(source, records, output_dir=None):
    destination = Path(output_dir) if output_dir else ROOT / "data"
    destination.mkdir(parents=True, exist_ok=True)
    items = {r['id']: r for r in records if r.get('id') and r.get('title')}
    payload = {"profile": None, "scraped_at": datetime.now(timezone.utc).isoformat(),
               "count": len(items), "matches": list(items.values())}
    path = destination / f"{source}_matches.json"
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    return path


def get(url, session=None, timeout=25, retries=3):
    client = session or requests.Session()
    for attempt in range(retries):
        try:
            response = client.get(url, headers=HEADERS, timeout=timeout)
            if response.status_code in (429,500,502,503,504) and attempt < retries-1:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError):
            if attempt == retries-1: raise
            time.sleep(2**attempt)
    raise RuntimeError('Unreachable retry state')


def robots_allowed(url, session=None):
    parsed=urlparse(url); robots=f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response=get(robots, session=session, timeout=10, retries=1)
        rp=RobotFileParser(); rp.parse(response.text.splitlines())
        return rp.can_fetch(USER_AGENT, url)
    except requests.RequestException:
        # fail closed when cannot establish policy
        return False


def html_links(source, seeds, *, session=None, limit=100, delay=1.5, strict_robots=True):
    """Discover candidate calls from official listing pages; no unbounded crawling."""
    client=session or requests.Session(); seen=set(); result=[]
    for seed in seeds:
        if strict_robots and not robots_allowed(seed, session=client):
            print(f"Skipping {seed}: robots policy unavailable/disallowed")
            continue
        soup=BeautifulSoup(get(seed, session=client).text, 'html.parser')
        for a in soup.find_all('a', href=True):
            title=' '.join(a.get_text(' ',strip=True).split())
            href=urljoin(seed,a['href'])
            if not title or len(title)<10 or href in seen: continue
            if urlparse(href).netloc != urlparse(seed).netloc: continue
            if not any(word in (title+' '+href).lower() for word in KEYWORDS): continue
            seen.add(href)
            result.append(canonical(source,href,title,summary=f"Discovered on official listing: {seed}",source_url=seed,record_type="discovered_link"))
            if len(result)>=limit: return result
        time.sleep(delay)
    return result


def ted_search(*, query='PD >= 20261001', limit=50, session=None):
    """Official anonymous TED Search API v3. Query syntax documented by TED."""
    endpoint='https://api.ted.europa.eu/v3/notices/search'
    body={"query":query,"fields":["publication-number","notice-title","publication-date","deadline-receipt-tender-date-lot"],"limit":limit,"page":1}
    response=(session or requests.Session()).post(endpoint,json=body,headers={**HEADERS,'Content-Type':'application/json'},timeout=45)
    response.raise_for_status()
    data=response.json()
    notices=data.get('notices',data.get('results',[]))
    if not isinstance(notices,list): raise ValueError('Unexpected TED response')
    output=[]
    def scalar(v):
        if isinstance(v,list):return scalar(v[0]) if v else ''
        if isinstance(v,dict):return next((str(x) for x in v.values() if isinstance(x,str)), '')
        return str(v or '')
    for notice in notices:
        number=scalar(notice.get('publication-number') or notice.get('publicationNumber'))
        if not number: continue
        title=scalar(notice.get('notice-title') or notice.get('title')) or f'TED notice {number}'
        url=f'https://ted.europa.eu/en/notice/-/detail/{number}'
        output.append(canonical('ted_procurement',url,title,call_identifier=number,summary='TED procurement notice',countries=[]))
    return output


def cordis_csv(url, *, session=None, limit=100):
    """Read an official CORDIS CSV export URL supplied by operator; avoid guessing download endpoints."""
    if urlparse(url).netloc not in ('cordis.europa.eu','data.europa.eu','www.cordis.europa.eu'):
        raise ValueError('CORDIS export must be an official EU host')
    response=get(url,session=session,timeout=60)
    text=response.content.decode('utf-8-sig')
    reader=csv.DictReader(io.StringIO(text))
    output=[]
    for row in reader:
        project_id=row.get('id') or row.get('rcn') or row.get('projectID')
        title=row.get('title') or row.get('acronym')
        if not project_id or not title: continue
        project_url=f'https://cordis.europa.eu/project/id/{project_id}'
        output.append(canonical('cordis_projects',project_url,title,summary=row.get('objective') or '',program=row.get('frameworkProgramme'),status='historical_project',countries=[]))
        if len(output)>=limit:break
    return output


def eu_grants_search(*, query, limit=50, session=None):
    """Use the same SEDIA endpoint as existing EU tender scraper; caller supplies a verified grants query."""
    endpoint='https://api.tech.ec.europa.eu/search-api/prod/rest/search'
    files={'query':('query.json',json.dumps(query),'application/json')}
    r=(session or requests.Session()).post(endpoint,params={'apiKey':'SEDIA','text':'***'},data={'pageSize':str(limit),'pageNumber':'1'},files=files,timeout=60)
    r.raise_for_status(); data=r.json(); output=[]
    for raw in data.get('results',[]):
        metadata=raw.get('metadata') or {}
        def first(key,default=None):
            val=metadata.get(key)
            return val[0] if isinstance(val,list) and val else default
        title=first('title') or raw.get('summary') or 'EU grant'
        link=raw.get('url')
        if not isinstance(link,str) or not link.startswith('http'): continue
        output.append(canonical('eu_grants',link,title,summary=raw.get('summary') or '',call_identifier=first('callIdentifier'),deadline=(first('deadlineDate') or '')[:10] or None))
    return output


def main(source, seeds=None, *, query=None):
    parser=argparse.ArgumentParser(description=f'{source}: funding scraper')
    parser.add_argument('--output-dir',default=None)
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--delay',type=float,default=1.5)
    parser.add_argument('--cordis-csv-url',default=os.environ.get('CORDIS_CSV_URL'))
    parser.add_argument('--ted-query',default=os.environ.get('TED_QUERY','PD >= 20261001'))
    parser.add_argument('--eu-grants-query',default=os.environ.get('EU_GRANTS_QUERY_JSON'))
    args=parser.parse_args()
    if source=='ted_procurement': records=ted_search(query=args.ted_query,limit=args.limit)
    elif source=='cordis_projects':
        if not args.cordis_csv_url: parser.error('Provide --cordis-csv-url with an official CORDIS CSV export')
        records=cordis_csv(args.cordis_csv_url,limit=args.limit)
    elif source=='eu_grants':
        if not args.eu_grants_query: parser.error('Provide --eu-grants-query with validated SEDIA grants query JSON')
        records=eu_grants_search(query=json.loads(args.eu_grants_query),limit=args.limit)
    else: records=html_links(source,seeds or [],limit=args.limit,delay=args.delay)
    path=save(source,records,args.output_dir)
    print(f'{source}: {len(records)} results -> {path}')
