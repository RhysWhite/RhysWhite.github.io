#!/usr/bin/env python3
"""Refresh DOI-level publication citation metrics from OpenAlex.

The website remains usable if OpenAlex is unavailable: existing metric data
are retained unless a complete new response is obtained.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLICATIONS = ROOT / "data" / "publications.json"
OUTPUT = ROOT / "data" / "publication-metrics.json"

OPENALEX = "https://api.openalex.org/works"
UA = "RhysWhiteWebsite/1.0 (+https://rhyswhite.github.io/)"


def main() -> int:
    data = json.loads(PUBLICATIONS.read_text(encoding="utf-8"))

    dois = sorted(
        {
            str(pub.get("doi") or "").strip().lower()
            for pub in data.get("publications", [])
            if pub.get("doi")
        }
    )

    if not dois:
        raise RuntimeError("No DOI-bearing publications found.")

    # OpenAlex supports OR filters with up to 100 values, so the complete
    # publication record can be refreshed in one request.
    doi_filter = "|".join(f"https://doi.org/{doi}" for doi in dois)

    params = urllib.parse.urlencode(
        {
            "filter": f"doi:{doi_filter}",
            "per_page": "100",
            "select": "doi,cited_by_count,id",
        }
    )

    req = urllib.request.Request(
        f"{OPENALEX}?{params}",
        headers={"User-Agent": UA, "Accept": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=45) as response:
        payload = json.load(response)

    results = payload.get("results") or []
    if not results:
        raise RuntimeError(
            "OpenAlex returned no matching works; refusing to overwrite last-known-good metrics."
        )

    metrics = {}

    for work in results:
        doi = str(work.get("doi") or "").strip().lower()
        doi = doi.removeprefix("https://doi.org/")

        if not doi:
            continue

        count = work.get("cited_by_count")
        if not isinstance(count, int):
            continue

        metrics[doi] = {
            "citations": count,
            "provider": "openalex",
            "openalex_id": work.get("id"),
        }

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "provider": "openalex",
        "metrics": metrics,
    }

    OUTPUT.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"OpenAlex metrics: {len(metrics)} matched works "
        f"from {len(dois)} DOI-bearing site records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
