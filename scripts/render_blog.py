#!/usr/bin/env python3
"""Render plain-English research notes from structured, human-reviewed data.

No third-party Python packages are required.

Published notes must correspond to an existing publication DOI. Draft notes
are ignored by the public renderer until explicitly marked "published".
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

from render_publications import esc, footer, header, rich_authors, rich_title


ROOT = Path(__file__).resolve().parents[1]
BLOG_DATA = ROOT / "data" / "blog-posts.json"
PUBLICATION_DATA = ROOT / "data" / "publications.json"
BLOG_DIR = ROOT / "blog"
POSTS_DIR = BLOG_DIR / "posts"


REQUIRED_PUBLISHED_FIELDS = [
    "slug",
    "doi",
    "note_date",
    "headline",
    "standfirst",
    "short_version",
    "question",
    "findings",
    "meaning",
    "limitations",
    "credit",
]


def parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field} must use YYYY-MM-DD format: {value!r}"
        ) from exc


def human_date(value: str) -> str:
    d = parse_iso_date(value, "date")
    return f"{d.day} {d.strftime('%B %Y')}"


def publication_lookup() -> dict[str, dict]:
    payload = json.loads(PUBLICATION_DATA.read_text(encoding="utf-8"))
    lookup = {}

    for pub in payload.get("publications", []):
        doi = str(pub.get("doi") or "").strip().lower()
        if doi:
            lookup[doi] = pub

    return lookup


def validate_posts(posts: list[dict], publications: dict[str, dict]) -> None:
    seen_slugs: set[str] = set()
    seen_dois: set[str] = set()

    for index, post in enumerate(posts, start=1):
        status = str(post.get("status") or "draft").strip().lower()

        if status not in {"draft", "published"}:
            raise ValueError(
                f"Post {index}: status must be 'draft' or 'published'."
            )

        slug = str(post.get("slug") or "").strip()

        if slug:
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
                raise ValueError(
                    f"Post {index}: invalid slug {slug!r}."
                )
            if slug in seen_slugs:
                raise ValueError(f"Duplicate blog slug: {slug}")
            seen_slugs.add(slug)

        # Drafts may be incomplete while they are being written.
        if status != "published":
            continue

        missing = [
            field
            for field in REQUIRED_PUBLISHED_FIELDS
            if post.get(field) in (None, "", [])
        ]
        if missing:
            raise ValueError(
                f"Published post {slug or index} is missing: "
                + ", ".join(missing)
            )

        doi = str(post["doi"]).strip().lower()

        if doi not in publications:
            raise ValueError(
                f"Published post {slug}: DOI {doi} is not present "
                "in data/publications.json."
            )

        if doi in seen_dois:
            raise ValueError(
                f"More than one published research note uses DOI {doi}."
            )
        seen_dois.add(doi)

        parse_iso_date(str(post["note_date"]), "note_date")

        paper_date = str(post.get("paper_date") or "").strip()
        if paper_date:
            parse_iso_date(paper_date, "paper_date")

        findings = post.get("findings")
        if not isinstance(findings, list) or not all(
            isinstance(item, str) and item.strip() for item in findings
        ):
            raise ValueError(
                f"Published post {slug}: findings must be a non-empty "
                "list of text statements."
            )

        media = post.get("media", [])
        if not isinstance(media, list):
            raise ValueError(
                f"Published post {slug}: media must be a list."
            )

        for item in media:
            if not isinstance(item, dict):
                raise ValueError(
                    f"Published post {slug}: each media item must be an object."
                )

            required = ["outlet", "title", "url", "date"]
            absent = [field for field in required if not item.get(field)]
            if absent:
                raise ValueError(
                    f"Published post {slug}: media item missing "
                    + ", ".join(absent)
                )

            parse_iso_date(str(item["date"]), "media date")

        headline_words = len(
            re.findall(r"\b[\w’'-]+\b", str(post["headline"]))
        )
        if headline_words > 14:
            print(
                f"WARNING: {slug} headline is {headline_words} words; "
                "consider tightening it for a general audience."
            )


def paper_date_for_sort(post: dict, pub: dict) -> date:
    paper_date = str(post.get("paper_date") or "").strip()
    if paper_date:
        return parse_iso_date(paper_date, "paper_date")

    year = int(pub.get("year") or 0)
    return date(year, 1, 1)


def render_media(media: list[dict]) -> str:
    if not media:
        return ""

    items = []

    for item in sorted(
        media,
        key=lambda x: parse_iso_date(str(x["date"]), "media date"),
        reverse=True,
    ):
        items.append(
            '<li>'
            f'<span class="media-date">{esc(human_date(str(item["date"])))}</span>'
            '<div>'
            f'<strong>{esc(item["outlet"])}</strong>'
            f'<a href="{esc(item["url"])}">{esc(item["title"])}</a>'
            '</div>'
            '</li>'
        )

    return (
        '<section class="note-section">'
        '<h2>In the media</h2>'
        '<p>Selected editorial coverage, interviews and broadcast reporting '
        'about this research.</p>'
        f'<ul class="media-list">{"".join(items)}</ul>'
        '</section>'
    )


def render_paper(pub: dict) -> str:
    doi = str(pub.get("doi") or "").strip()
    title = rich_title(str(pub.get("title") or ""))
    authors = rich_authors(str(pub.get("authors") or ""))
    journal = esc(pub.get("journal"))
    citation = esc(pub.get("citation"))
    year = esc(pub.get("year"))

    metadata = [authors]
    if journal:
        metadata.append(f"<i>{journal}</i>")
    if citation:
        metadata.append(citation)
    if year:
        metadata.append(year)

    return (
        '<section class="note-section paper-box">'
        '<p class="eyebrow">The paper</p>'
        f'<h2>{title}</h2>'
        f'<p>{" · ".join(metadata)}</p>'
        f'<a class="button" href="https://doi.org/{esc(doi)}">Read the paper →</a>'
        '</section>'
    )


def retrospective_label(post: dict, pub: dict) -> str:
    note_date = parse_iso_date(str(post["note_date"]), "note_date")
    pub_year = int(pub.get("year") or 0)

    if pub_year and pub_year < note_date.year:
        if post.get("paper_date"):
            published = human_date(str(post["paper_date"]))
        else:
            published = str(pub_year)

        return (
            f"From the archive · Paper published {published} · "
            f"Research note added {human_date(str(post['note_date']))}"
        )

    return f"Research note · {human_date(str(post['note_date']))}"


def note_text(value: object, post: dict) -> str:
    """Escape note prose, then safely italicise declared scientific terms."""
    rendered = esc(str(value))

    raw_terms = post.get("italics", [])
    if not isinstance(raw_terms, list):
        raise ValueError("Blog post 'italics' must be a list.")

    terms = sorted(
        {str(term).strip() for term in raw_terms if str(term).strip()},
        key=len,
        reverse=True,
    )

    replacements = {}

    for index, term in enumerate(terms):
        safe_term = esc(term)
        token = f"@@BLOGITALIC{index}@@"
        rendered = rendered.replace(safe_term, token)
        replacements[token] = f"<i>{safe_term}</i>"

    for token, replacement in replacements.items():
        rendered = rendered.replace(token, replacement)

    return rendered


def render_post(post: dict, pub: dict) -> str:
    slug = str(post["slug"])
    canonical = f"https://rhyswhite.github.io/blog/posts/{slug}/"

    findings = "".join(
        f"<li>{note_text(item, post)}</li>"
        for item in post["findings"]
    )

    media = render_media(post.get("media", []))

    return f'''<!doctype html>
<html lang="en-NZ">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(post["headline"])} — Rhys White</title>
<meta name="description" content="{esc(post["standfirst"])}">
<link rel="canonical" href="{canonical}">
<link rel="icon" href="/assets/img/mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/css/site.css">
</head>
<body>
{header("blog")}
<main id="main">
<article class="research-note">
<header class="note-hero">
<div class="narrow">
<p class="eyebrow">Research note</p>
<p class="note-status">{esc(retrospective_label(post, pub))}</p>
<h1>{note_text(post["headline"], post)}</h1>
<p class="lede">{note_text(post["standfirst"], post)}</p>
</div>
</header>

<div class="narrow note-body">

<section class="note-section note-short">
<h2>The short version</h2>
<p>{note_text(post["short_version"], post)}</p>
</section>

<section class="note-section">
<h2>What were we trying to find out?</h2>
<p>{note_text(post["question"], post)}</p>
</section>

<section class="note-section">
<h2>What did we find?</h2>
<ul class="note-findings">{findings}</ul>
</section>

<section class="note-section">
<h2>What does it mean?</h2>
<p>{note_text(post["meaning"], post)}</p>
</section>

<section class="note-section">
<h2>What does it not show?</h2>
<p>{note_text(post["limitations"], post)}</p>
</section>

{render_paper(pub)}

<section class="note-section">
<h2>Credit</h2>
<p>{note_text(post["credit"], post)}</p>
</section>

{media}

<p class="note-back"><a href="/blog/">← All research notes</a></p>

</div>
</article>
</main>
{footer()}
<script src="/assets/js/site.js"></script>
</body>
</html>'''


def render_index(entries: list[tuple[dict, dict]]) -> str:
    if entries:
        cards = []

        for post, pub in entries:
            slug = esc(post["slug"])
            label = retrospective_label(post, pub)

            cards.append(
                '<article class="note-card">'
                f'<p class="note-card-meta">{esc(label)}</p>'
                f'<h2><a href="/blog/posts/{slug}/">'
                f'{note_text(post["headline"], post)}</a></h2>'
                f'<p>{note_text(post["standfirst"], post)}</p>'
                f'<a class="note-read" href="/blog/posts/{slug}/">'
                'Read the plain-English summary →</a>'
                '</article>'
            )

        content = f'<div class="notes-grid">{"".join(cards)}</div>'
    else:
        content = (
            '<div class="note-empty">'
            '<h2>Research notes are being prepared.</h2>'
            '<p>Retrospective notes will begin with papers published from '
            '2022 onward. New papers will be added as they are published.</p>'
            '</div>'
        )

    return f'''<!doctype html>
<html lang="en-NZ">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Research notes — Rhys White</title>
<meta name="description" content="Short, plain-English explanations of published research in microbial genomics, genomic epidemiology and antimicrobial resistance.">
<link rel="canonical" href="https://rhyswhite.github.io/blog/">
<link rel="icon" href="/assets/img/mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/css/site.css">
</head>
<body>
{header("blog")}
<main id="main">
<section class="page-hero">
<div class="container">
<p class="eyebrow">Blog</p>
<h1>Research notes.</h1>
<p class="lede">Short, plain-English explanations of published research: what we asked, what we found, what the results mean, and what they do not show.</p>
</div>
</section>

<section class="section white">
<div class="container">
{content}
</div>
</section>
</main>
{footer()}
<script src="/assets/js/site.js"></script>
</body>
</html>'''


def main() -> None:
    blog_payload = json.loads(BLOG_DATA.read_text(encoding="utf-8"))
    publications = publication_lookup()
    posts = blog_payload.get("posts", [])

    if not isinstance(posts, list):
        raise ValueError("data/blog-posts.json: posts must be a list.")

    validate_posts(posts, publications)

    published: list[tuple[dict, dict]] = []

    for post in posts:
        if str(post.get("status") or "draft").lower() != "published":
            continue

        doi = str(post["doi"]).strip().lower()
        published.append((post, publications[doi]))

    published.sort(
        key=lambda pair: paper_date_for_sort(pair[0], pair[1]),
        reverse=True,
    )

    BLOG_DIR.mkdir(parents=True, exist_ok=True)

    # blog/posts/ contains generated HTML only. Rebuild it cleanly so removed
    # or renamed posts cannot leave stale public pages behind.
    if POSTS_DIR.exists():
        shutil.rmtree(POSTS_DIR)
    POSTS_DIR.mkdir(parents=True)

    for post, pub in published:
        out = POSTS_DIR / str(post["slug"]) / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_post(post, pub), encoding="utf-8")

    (BLOG_DIR / "index.html").write_text(
        render_index(published),
        encoding="utf-8",
    )

    print(
        f"Rendered {len(published)} published research notes "
        f"from {len(posts)} total blog records."
    )


if __name__ == "__main__":
    main()
