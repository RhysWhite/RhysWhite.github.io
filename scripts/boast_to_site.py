#!/usr/bin/env python3
"""Convert the newest NEXCISION boast Snapshot into tiny website JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def as_number(value: Any) -> Any:
    if isinstance(value, (int, float, str)):
        return value
    if isinstance(value, dict):
        # boast snapshots encode typed metric values; accept common shapes.
        for key in ("value", "integer", "float", "number", "string"):
            if key in value:
                return as_number(value[key])
    return None


def metric_value(metric: dict[str, Any]) -> Any:
    return as_number(metric.get("value"))


def identity_text(result: dict[str, Any]) -> str:
    ident = result.get("identity")
    if isinstance(ident, str):
        return ident.lower()
    if isinstance(ident, dict):
        for key in ("canonical", "value", "display"):
            if ident.get(key):
                return str(ident[key]).lower()
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot_dir", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    files = sorted(args.snapshot_dir.glob("*.json"))
    if not files:
        raise SystemExit("No boast snapshots found; leaving current site metric JSON untouched.")
    newest = files[-1]
    snap = json.loads(newest.read_text(encoding="utf-8"))
    wanted = {
        ("conda:bioconda/nexcision", "downloads"): "downloads",
        ("github:rhyswhite/nexcision", "release_downloads"): "release_downloads",
        ("github:rhyswhite/nexcision", "stars"): "stars",
        ("doi:10.64898/2026.07.26.740842", "citations"): "citations",
        ("doi:10.64898/2026.07.26.740842", "fwci"): "fwci",
        ("doi:10.64898/2026.07.26.740842", "altmetric"): "altmetric",
    }
    output: dict[str, Any] = {"updated": snap.get("created_at"), "source": "boast", "snapshot": newest.name, "metrics": {}}
    for result in snap.get("results", []) or []:
        identity = identity_text(result)
        outcome = result.get("outcome") or {}
        for metric in outcome.get("metrics", []) or []:
            name = str(metric.get("name") or "").lower()
            site_key = wanted.get((identity, name))
            if not site_key:
                continue
            # For citations choose OpenAlex where multiple providers report the same metric.
            provider = str(metric.get("provider") or result.get("provider") or "").lower()
            if site_key == "citations" and provider and provider != "openalex":
                continue
            value = metric_value(metric)
            if value is not None:
                output["metrics"][site_key] = {"value": value, "provider": provider or None, "as_of": metric.get("as_of")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(output['metrics'])} website metrics from {newest.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
