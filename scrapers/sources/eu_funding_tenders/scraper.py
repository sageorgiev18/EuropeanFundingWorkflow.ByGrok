#!/usr/bin/env python3
"""
Scraper for EU Funding & Tenders Portal – Calls for Tenders.
Uses the official public SEDIA Search API.
Matches results against a company profile and writes matches for alerting.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
API_KEY = "SEDIA"

# Paths relative to this file
HERE = Path(__file__).parent
PROFILE_PATH = HERE / "company_profile.json"
OUTPUT_PATH = HERE.parent.parent.parent / "data" / "eu_funding_tenders_matches.json"


def load_profile():
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_query(open_only=True):
    """Query for calls for tenders (type=0)."""
    status = ["31094501", "31094502"] if open_only else ["31094501", "31094502", "31094503"]
    return {
        "bool": {
            "must": [
                {"terms": {"type": ["0"]}},
                {"terms": {"status": status}},
            ]
        }
    }


def fetch_page(query, page=1, page_size=50):
    files = {
        "query": ("query.json", json.dumps(query), "application/json"),
    }
    data = {
        "pageSize": str(page_size),
        "pageNumber": str(page),
    }
    params = {"apiKey": API_KEY, "text": "***"}
    resp = requests.post(API_URL, params=params, data=data, files=files, timeout=60)
    resp.raise_for_status()
    return resp.json()


def normalize_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def score_match(item, profile):
    """Simple keyword-based relevance score (0-1)."""
    text_parts = [
        item.get("summary", ""),
        item.get("content", ""),
        " ".join(item.get("metadata", {}).get("title", [])),
    ]
    # Include main CPV description if present
    meta = item.get("metadata", {})
    for key in ("mainCpv", "mainCpvCode"):
        if key in meta:
            text_parts.append(" ".join(str(x) for x in meta[key]))

    full_text = normalize_text(" ".join(text_parts))
    if not full_text:
        return 0.0

    keywords = [k.lower() for k in profile.get("keywords", [])]
    if not keywords:
        return 0.0

    hits = sum(1 for kw in keywords if kw in full_text)
    # Bonus for exact multi-word phrases
    phrase_bonus = sum(0.5 for kw in keywords if " " in kw and kw in full_text)
    score = min(1.0, (hits + phrase_bonus) / max(len(keywords), 1))
    return round(score, 3)


def extract_opportunity(raw):
    """Map raw API result to our schema."""
    meta = raw.get("metadata", {})
    title = " ".join(meta.get("title", [])) or raw.get("summary", "Untitled")
    deadline = None
    if meta.get("deadlineDate"):
        deadline = meta["deadlineDate"][0][:10]  # YYYY-MM-DD

    return {
        "id": meta.get("identifier", [raw.get("reference")])[0],
        "call_identifier": meta.get("callIdentifier", [None])[0],
        "title": title,
        "summary": raw.get("summary"),
        "url": raw.get("url"),
        "status": meta.get("status", [None])[0],
        "start_date": meta.get("startDate", [None])[0],
        "deadline": deadline,
        "source": "eu_funding_tenders",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "raw_metadata_keys": list(meta.keys()),
    }


def main(max_pages=3):
    profile = load_profile()
    min_score = profile.get("min_score", 0.15)
    query = build_query(open_only=True)

    matches = []
    for page in range(1, max_pages + 1):
        print(f"Fetching page {page}...")
        data = fetch_page(query, page=page, page_size=50)
        results = data.get("results", [])
        if not results:
            break

        for raw in results:
            score = score_match(raw, profile)
            if score >= min_score:
                opp = extract_opportunity(raw)
                opp["match_score"] = score
                opp["matched_keywords"] = [
                    kw for kw in profile.get("keywords", [])
                    if kw.lower() in normalize_text(
                        (raw.get("summary") or "") + " " + " ".join(raw.get("metadata", {}).get("title", []))
                    )
                ]
                matches.append(opp)

    matches.sort(key=lambda x: x["match_score"], reverse=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "profile": profile["name"],
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "count": len(matches),
            "matches": matches,
        }, f, indent=2, ensure_ascii=False)

    print(f"Found {len(matches)} matching opportunities (score >= {min_score}).")
    print(f"Wrote results to {OUTPUT_PATH}")
    return matches


if __name__ == "__main__":
    main()
