#!/usr/bin/env python3
"""Discover public works from ORCID, enrich DOI records with Crossref, and re-render.

Design goals:
- ORCID is the discovery source.
- Existing records are last-known-good data, so an API outage cannot empty the site.
- Curated research labels live separately in publication-overrides.json.
- No third-party Python dependencies are required.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "publications.json"
OVERRIDES_FILE = ROOT / "data" / "publication-overrides.json"
ORCID_ID = "0000-0001-6620-758X"
ORCID_API = "https://pub.orcid.org/v3.0"
ORCID_TOKEN_URL = "https://orcid.org/oauth/token"
CROSSREF_API = "https://api.crossref.org/works/"
UA = "RhysWhiteWebsite/1.0 (+https://rhyswhite.github.io/)"


def request_json(url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None, timeout: int = 30) -> Any:
    h = {"Accept": "application/json", "User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def access_token() -> str:
    """Return the supported ORCID /read-public token for API reads."""
    token = os.getenv("ORCID_ACCESS_TOKEN", "").strip()
    if token:
        return token
    client_id = os.getenv("ORCID_CLIENT_ID", "").strip()
    client_secret = os.getenv("ORCID_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Set ORCID_ACCESS_TOKEN or both ORCID_CLIENT_ID and ORCID_CLIENT_SECRET.")
    payload = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "scope": "/read-public",
        }
    ).encode()
    result = request_json(ORCID_TOKEN_URL, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    token = str(result.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("ORCID did not return an access token.")
    return token


def nested_value(obj: Any, *keys: str) -> str:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    if isinstance(cur, dict) and "value" in cur:
        cur = cur.get("value")
    return str(cur or "").strip()


def extract_doi(summary: dict[str, Any]) -> str:
    ids = ((summary.get("external-ids") or {}).get("external-id") or [])
    for ident in ids:
        if str(ident.get("external-id-type") or "").lower() == "doi":
            return str(ident.get("external-id-value") or "").strip().lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    return ""


def orcid_works(token: str) -> list[dict[str, Any]]:
    result = request_json(
        f"{ORCID_API}/{ORCID_ID}/works",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.orcid+json"},
    )
    works: list[dict[str, Any]] = []
    for group in result.get("group", []) or []:
        summaries = group.get("work-summary", []) or []
        if not summaries:
            continue
        # Prefer a DOI-bearing summary, because DOI is our stable merge key.
        summary = next((s for s in summaries if extract_doi(s)), summaries[0])
        doi = extract_doi(summary)
        if not doi:
            continue
        year_raw = nested_value(summary, "publication-date", "year")
        try:
            year = int(year_raw)
        except ValueError:
            year = 0
        title = nested_value(summary, "title", "title")
        journal = nested_value(summary, "journal-title")
        works.append(
            {
                "year": year,
                "title": title,
                "authors": "",
                "journal": journal,
                "citation": "",
                "doi": doi,
                "tags": [],
                "labels": [],
                "source": "orcid",
            }
        )
    return works


def strip_markup(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value or "")
    return html.unescape(value).strip()


def initials(given: str) -> str:
    return "".join(part[0].upper() for part in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", given or "") if part)


def author_string(authors: list[dict[str, Any]]) -> str:
    names: list[str] = []
    for author in authors:
        family = str(author.get("family") or "").strip()
        given = str(author.get("given") or "").strip()
        if family:
            names.append(f"{family} {initials(given)}".strip())
    if len(names) > 4:
        return ", ".join(names[:3]) + " et al."
    return ", ".join(names)


def crossref_record(doi: str) -> dict[str, Any]:
    url = CROSSREF_API + urllib.parse.quote(doi, safe="")
    payload = request_json(url)
    msg = payload.get("message", {}) or {}
    title_list = msg.get("title") or []
    container = msg.get("container-title") or []
    title = strip_markup(str(title_list[0])) if title_list else ""
    journal = strip_markup(str(container[0])) if container else ""
    year = 0
    for field in ("published-print", "published-online", "published", "issued", "created"):
        parts = ((msg.get(field) or {}).get("date-parts") or [])
        if parts and parts[0]:
            try:
                year = int(parts[0][0])
                break
            except (ValueError, TypeError):
                pass
    volume = str(msg.get("volume") or "").strip()
    issue = str(msg.get("issue") or "").strip()
    page = str(msg.get("page") or msg.get("article-number") or "").strip()
    citation = volume
    if volume and issue:
        citation += f"({issue})"
    if page:
        citation = f"{citation}:{page}" if citation else page
    return {
        "year": year,
        "title": title,
        "authors": author_string(msg.get("author") or []),
        "journal": journal,
        "citation": citation,
    }


def infer_tags_labels(title: str) -> tuple[list[str], list[str]]:
    low = title.lower()
    tags: list[str] = []
    if any(k in low for k in ("outbreak", "transmission", "ward-based", "neonatal", "nicu", "hospital surveillance")):
        tags.append("outbreak")
    if any(k in low for k in ("resistance", "resistant", "plasmid", "carbapenem", "colistin", "mcr", "mrsa", "oxa-", "antimicrobial", "mobile dna", "mobile element")):
        tags.append("mobile")
    if any(k in low for k in ("nanopore", "decentralized", "decentralised", "front-line", "clinical laboratory", "prospective", "ultra-rapid")):
        tags.append("implementation")
    if any(k in low for k in ("population", "phylogen", "lineage", "st131", "st1193", "comparative genomics", "evolution", "fitness", "metabolism", "genomic success")):
        tags.append("population")
    if any(k in low for k in ("chlamydia", "avian", "livestock", "companion animal", "koala", "pantoea", "pasteurella", "veterinary")):
        tags.append("comparative")
    if any(k in low for k in ("nexcision", "nexus", "software", "method", "validation", "workflow", "herro error correction")):
        tags.append("methods")
    labels: list[str] = []
    vocabulary = [
        ("nanopore", "nanopore"), ("plasmid", "plasmids"), ("outbreak", "outbreak"),
        ("st131", "ST131"), ("mrsa", "MRSA"), ("oxa-48", "OXA-48"),
        ("mcr", "mcr"), ("klebsiella", "Klebsiella"), ("chlamydia", "Chlamydia"),
    ]
    for needle, label in vocabulary:
        if needle in low and label not in labels:
            labels.append(label)
        if len(labels) == 3:
            break
    return tags, labels


def merge(existing: list[dict[str, Any]], discovered: list[dict[str, Any]], overrides: dict[str, Any]) -> list[dict[str, Any]]:
    by_doi = {str(p.get("doi") or "").lower(): dict(p) for p in existing if p.get("doi")}
    # Some legitimate publications have no DOI. Keep those curated local records
    # across ORCID syncs instead of silently dropping them.
    without_doi = [dict(p) for p in existing if not p.get("doi")]

    for work in discovered:
        doi = work["doi"].lower()
        current = by_doi.get(doi)
        record = dict(current or {})

        # Existing local bibliographic data is curated and therefore wins. ORCID
        # only fills fields that are currently absent. This prevents an online-
        # first date or abbreviated title from silently changing the public CV.
        for key, value in work.items():
            if value not in ("", 0, [], None) and record.get(key) in ("", 0, [], None):
                record[key] = value

        try:
            crossref = crossref_record(doi)
        except Exception as exc:  # provider failure must not erase good local metadata
            print(f"Crossref warning for {doi}: {exc}", file=sys.stderr)
            crossref = {}
        for key, value in crossref.items():
            if value not in ("", 0, None) and record.get(key) in ("", 0, None):
                record[key] = value

        override = overrides.get(doi, {})
        if override:
            record.update({k: v for k, v in override.items() if k != "exclude"})
        if not record.get("tags") or not record.get("labels"):
            tags, labels = infer_tags_labels(str(record.get("title") or ""))
            record["tags"] = record.get("tags") or tags
            record["labels"] = record.get("labels") or labels
        record["doi"] = doi
        record["source"] = record.get("source") or "orcid"
        by_doi[doi] = record

    # Apply overrides to last-known-good records too, not only works returned by
    # the latest ORCID request. A DOI can be suppressed with {"exclude": true}.
    publications: list[dict[str, Any]] = []
    for doi, record in by_doi.items():
        override = overrides.get(doi, {})
        if override.get("exclude") is True:
            continue
        if override:
            record.update({k: v for k, v in override.items() if k != "exclude"})
        publications.append(record)

    publications.extend(without_doi)

    # Stable year sort keeps the curated order within a year.
    publications.sort(key=lambda p: int(p.get("year") or 0), reverse=True)
    return publications


def main() -> int:
    existing_data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    overrides = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8")) if OVERRIDES_FILE.exists() else {}
    token = access_token()
    discovered = orcid_works(token)
    if not discovered:
        raise RuntimeError("ORCID returned no DOI-bearing public works; refusing to overwrite last-known-good data.")
    publications = merge(existing_data.get("publications", []), discovered, overrides)
    output = {"orcid": ORCID_ID, "generated": date.today().isoformat(), "publications": publications}
    DATA_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "render_publications.py")], check=True)
    print(f"ORCID discovery: {len(discovered)} DOI-bearing works; site dataset: {len(publications)} records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
