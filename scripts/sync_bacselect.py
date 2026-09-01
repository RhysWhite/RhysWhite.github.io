#!/usr/bin/env python3
"""Normalize canonical BacSelect site metadata for RhysWhite.github.io.

The canonical source is https://bacselect.github.io/data/site.json.
This script deliberately keeps frozen selector/reference metadata separate from
monthly release status. It writes deterministic JSON and fails closed on an
unexpected source shape.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_URL = "https://bacselect.github.io/data/site.json"
RELEASE_RE = re.compile(r"^\d{4}\.\d{2}$")


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        fail(f"{label} must be a positive integer")
    return value


def nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} must be a non-empty string")
    return value.strip()


def load_json_from_url(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "RhysWhite.github.io BacSelect metadata sync"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            fail(f"BacSelect metadata returned HTTP {response.status}")
        payload = response.read()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        fail(f"BacSelect metadata is not valid JSON: {exc}")
    if not isinstance(data, dict):
        fail("BacSelect metadata root must be an object")
    return data


def load_json_from_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"unable to read BacSelect metadata from {path}: {exc}")
    if not isinstance(data, dict):
        fail("BacSelect metadata root must be an object")
    return data


def normalize(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("resource") != "BacSelect":
        fail("resource must be exactly 'BacSelect'")

    foundation = data.get("foundation")
    panel = data.get("panel")
    reference = data.get("reference_panel")
    monthly = data.get("monthly_release")

    if not isinstance(foundation, dict):
        fail("foundation must be an object")
    if not isinstance(panel, dict):
        fail("panel must be an object")
    if not isinstance(reference, dict):
        fail("reference_panel must be an object")
    if not isinstance(monthly, dict):
        fail("monthly_release must be an object")

    eligible = positive_int(foundation.get("eligible_genomes"), "foundation.eligible_genomes")
    species = positive_int(foundation.get("species_groups"), "foundation.species_groups")
    features = positive_int(foundation.get("structural_features"), "foundation.structural_features")
    if foundation.get("is_bacselect_release") is not False:
        fail("foundation.is_bacselect_release must be false")

    min_n = positive_int(panel.get("min_n"), "panel.min_n")
    max_n = positive_int(panel.get("max_n"), "panel.max_n")
    if min_n > max_n:
        fail("panel.min_n cannot exceed panel.max_n")

    presets = panel.get("presets")
    if not isinstance(presets, list) or not presets:
        fail("panel.presets must be a non-empty array")
    normalized_presets = [positive_int(v, "panel.presets item") for v in presets]
    if normalized_presets != sorted(set(normalized_presets)):
        fail("panel.presets must be unique and ascending")
    if normalized_presets[0] < min_n or normalized_presets[-1] > max_n:
        fail("panel.presets must fall inside min_n/max_n")

    selector = nonempty_string(reference.get("selector"), "reference_panel.selector")
    selector_version = nonempty_string(
        reference.get("selector_version"),
        "reference_panel.selector_version",
    )
    if reference.get("validated") is not True:
        fail("reference_panel.validated must be true")

    published = monthly.get("published")
    if not isinstance(published, bool):
        fail("monthly_release.published must be boolean")
    release = monthly.get("release")
    if published:
        if not isinstance(release, str) or not RELEASE_RE.fullmatch(release):
            fail("published monthly_release.release must match YYYY.MM")
    elif release is not None:
        fail("unpublished monthly_release.release must be null")

    status_label = nonempty_string(
        monthly.get("status_label"),
        "monthly_release.status_label",
    )
    next_update = monthly.get("next_scheduled_update_utc")
    if next_update is not None and not isinstance(next_update, str):
        fail("monthly_release.next_scheduled_update_utc must be string or null")

    return {
        "schema_version": 1,
        "source": DEFAULT_URL,
        "resource": "BacSelect",
        "foundation": {
            "eligible_genomes": eligible,
            "species_groups": species,
            "structural_features": features,
        },
        "panel": {
            "min_n": min_n,
            "max_n": max_n,
            "presets": normalized_presets,
        },
        "reference_panel": {
            "selector": selector,
            "selector_version": selector_version,
            "validated": True,
        },
        "monthly_release": {
            "published": published,
            "release": release,
            "status_label": status_label,
            "next_scheduled_update_utc": next_update,
        },
    }



def replace_data_text(
    text: str,
    attribute: str,
    value: str,
    expected: int,
    label: str,
) -> str:
    pattern = re.compile(
        rf'(<(?P<tag>[A-Za-z][A-Za-z0-9:-]*)\b'
        rf'[^>]*\b{re.escape(attribute)}\b[^>]*>)'
        rf'([^<]*)'
        rf'(</(?P=tag)>)'
    )

    def repl(match: re.Match[str]) -> str:
        return match.group(1) + value + match.group(4)

    text, count = pattern.subn(repl, text)

    if count != expected:
        fail(
            f"{label}: expected {expected} elements with "
            f"{attribute}, found {count}"
        )

    return text


def render_html(root: Path, data: dict[str, Any]) -> None:
    foundation = data["foundation"]
    panel = data["panel"]
    reference = data["reference_panel"]
    monthly = data["monthly_release"]

    published = monthly["published"] is True

    if published:
        monthly_label = "Current monthly release"
        monthly_status = monthly["release"]
        monthly_link = "Open current BacSelect →"
    else:
        monthly_label = "Monthly release series"
        monthly_status = monthly["status_label"]
        monthly_link = "BacSelect status →"

    values = {
        "data-bacselect-selector-version": reference["selector_version"],
        "data-bacselect-foundation-genomes": f'{foundation["eligible_genomes"]:,}',
        "data-bacselect-foundation-species": f'{foundation["species_groups"]:,}',
        "data-bacselect-min-n": str(panel["min_n"]),
        "data-bacselect-max-n": str(panel["max_n"]),
        "data-bacselect-monthly-label": monthly_label,
        "data-bacselect-monthly-status": monthly_status,
        "data-bacselect-monthly-link": monthly_link,
    }

    pages = [
        (
            root / "index.html",
            {
                "data-bacselect-selector-version": 1,
                "data-bacselect-foundation-genomes": 1,
                "data-bacselect-foundation-species": 1,
                "data-bacselect-min-n": 1,
                "data-bacselect-max-n": 1,
                "data-bacselect-monthly-label": 1,
                "data-bacselect-monthly-status": 1,
                "data-bacselect-monthly-link": 1,
            },
        ),
        (
            root / "software/index.html",
            {
                "data-bacselect-selector-version": 2,
                "data-bacselect-foundation-genomes": 1,
                "data-bacselect-foundation-species": 1,
                "data-bacselect-min-n": 1,
                "data-bacselect-max-n": 1,
                "data-bacselect-monthly-label": 1,
                "data-bacselect-monthly-status": 1,
                "data-bacselect-monthly-link": 1,
            },
        ),
    ]

    for page, expected in pages:
        if not page.is_file():
            fail(f"missing page for BacSelect rendering: {page}")

        page_text = page.read_text(encoding="utf-8")

        for attribute, count in expected.items():
            page_text = replace_data_text(
                page_text,
                attribute,
                values[attribute],
                count,
                str(page),
            )

        page.write_text(page_text, encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url")
    source.add_argument("--source-file", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--render-root", type=Path)
    args = parser.parse_args()

    if args.url:
        raw = load_json_from_url(args.url)
    else:
        raw = load_json_from_file(args.source_file)

    normalized = normalize(raw)
    text = json.dumps(normalized, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")

    if args.render_root is not None:
        render_html(args.render_root, normalized)

    print(
        "BacSelect metadata sync: PASS "
        f"(monthly published={str(normalized['monthly_release']['published']).lower()})"
    )


if __name__ == "__main__":
    main()
