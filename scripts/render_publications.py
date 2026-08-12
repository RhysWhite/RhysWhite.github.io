#!/usr/bin/env python3
"""Render Publications and CV pages from data/publications.json.

Standard-library only so scheduled website updates need no Python package install.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "publications.json"
OVERRIDES = ROOT / "data" / "publication-overrides.json"
METRICS = ROOT / "data" / "publication-metrics.json"
BLOG_DATA = ROOT / "data" / "blog-posts.json"
PUBLICATIONS_OUT = ROOT / "publications" / "index.html"
CV_OUT = ROOT / "cv" / "index.html"

ORCID = "0000-0001-6620-758X"
SCHOLAR = "https://scholar.google.com/citations?user=NwdWAb4AAAAJ&hl=en"
EMAIL = "rhys.white@phfscience.nz"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def rich_title(value: str) -> str:
    """Escape a title and add conservative scientific-name/gene typography."""
    text = esc(value)
    replacements = [
        (r"\b(Klebsiella pneumoniae)\b", r"<i>\1</i>"),
        (r"\b(Klebsiella variicola)\b", r"<i>\1</i>"),
        (r"\b(Escherichia coli)\b", r"<i>\1</i>"),
        (r"\b(Staphylococcus aureus)\b", r"<i>\1</i>"),
        (r"\b(Chlamydia psittaci)\b", r"<i>\1</i>"),
        (r"\b(Chlamydia pecorum)\b", r"<i>\1</i>"),
        (r"\b(Chlamydia abortus)\b", r"<i>\1</i>"),
        (r"\b(Clostridioides difficile)\b", r"<i>\1</i>"),
        (r"\b(Pantoea stewartii)\b", r"<i>\1</i>"),
        (r"\b(Corvus orru)\b", r"<i>\1</i>"),
        (r"\b(Pezoporus flaviventris)\b", r"<i>\1</i>"),
        (r"\b(Pasteurella multocida)\b", r"<i>\1</i>"),
        (r"\b(blaOXA-48)\b", r"<i>bla</i><sub>OXA-48</sub>"),
        (r"\b(mcr)(?=[-\s])", r"<i>mcr</i>"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def rich_authors(value: str) -> str:
    text = esc(value)
    return re.sub(r"\bWhite RT\b", r"<strong>White RT</strong>", text)


def header(active: str) -> str:
    links = [
        ("Research", "/research/", "research"),
        ("Publications", "/publications/", "publications"),
        ("Software", "/software/", "software"),
        ("Blog", "/blog/", "blog"),
        ("CV", "/cv/", "cv"),
        ("About", "/about/", "about"),
    ]
    rendered = "".join(
        f'<a href="{url}"' + (' aria-current="page"' if key == active else "") + f'>{label}</a>'
        for label, url, key in links
    )
    return f'''<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header"><div class="container nav-wrap"><a class="brand" href="/" aria-label="Rhys White home"><img src="/assets/img/mark.svg" alt=""><span>Rhys White</span></a><button class="nav-toggle" type="button" aria-expanded="false" aria-controls="main-nav">Menu</button><nav class="nav" id="main-nav" aria-label="Primary">{rendered}</nav></div></header>'''


def footer() -> str:
    return '''<footer class="site-footer"><div class="container"><div class="footer-grid"><div><h2>Rhys White</h2><p>Microbial genomics · genomic epidemiology · antimicrobial resistance · research software.</p></div><div><h3>Navigate</h3><div class="footer-links"><a href="/research/">Research</a><a href="/publications/">Publications</a><a href="/software/">Software</a><a href="/blog/">Blog</a><a href="/cv/">CV</a><a href="/about/">About</a></div></div><div><h3>Connect</h3><div class="footer-links"><a href="mailto:rhys.white@phfscience.nz">Email</a><a href="https://github.com/RhysWhite">GitHub</a><a href="https://orcid.org/0000-0001-6620-758X">ORCID</a><a href="https://scholar.google.com/citations?user=NwdWAb4AAAAJ&amp;hl=en">Google Scholar</a><a href="https://www.researchgate.net/profile/Rhys-White-2">ResearchGate</a><a href="https://bsky.app/profile/rhystwhite.bsky.social">Bluesky</a><a href="https://x.com/RhysTWhite">X</a></div></div></div><div class="footer-bottom"><span>© <span data-year-now>2026</span> Rhys White</span><span>Personal website. Views are my own.</span></div></div></footer>'''


def pub_target(pub: dict) -> str:
    doi = str(pub.get("doi") or "").strip()
    if doi:
        return f"https://doi.org/{esc(doi)}"
    return esc(str(pub.get("url") or "").strip())


def pub_article(pub: dict) -> str:
    year = int(pub.get("year") or 0)
    tags = [str(t).strip().lower() for t in pub.get("tags", []) if str(t).strip()]
    labels = [str(t).strip() for t in pub.get("labels", []) if str(t).strip()]
    if pub.get("type") == "preprint" and "preprint" not in [x.lower() for x in labels]:
        labels.insert(0, "preprint")
    doi = str(pub.get("doi") or "").strip()
    target = pub_target(pub)
    label_html = "".join(f'<span class="pub-tag">{esc(label)}</span>' for label in labels)

    blog_html = ""
    blog_slug = str(pub.get("blog_slug") or "").strip()
    if blog_slug:
        blog_html = (
            f'<a class="pub-note-link" href="/blog/posts/{esc(blog_slug)}/">'
            'Plain-English summary →</a>'
        )

    citation_html = ""
    citation_count = pub.get("openalex_citations")
    openalex_url = str(pub.get("openalex_url") or "").strip()
    if isinstance(citation_count, int) and citation_count > 0:
        citation_text = f"OpenAlex citations: {citation_count}"
        if openalex_url:
            citation_html = (
                f'<a class="pub-citations" href="{esc(openalex_url)}">'
                f'{citation_text}</a>'
            )
        else:
            citation_html = f'<span class="pub-citations">{citation_text}</span>'

    impact = ""
    if doi:
        impact = (
            '<div class="pub-impact">'
            f'{citation_html}'
            f'<div class="altmetric-embed" data-badge-type="donut" data-badge-popover="right" '
            f'data-hide-no-mentions="true" data-doi="{esc(doi)}"></div>'
            f'<a class="pub-doi" href="{target}">DOI →</a>'
            '</div>'
        )
    elif target:
        impact = f'<div class="pub-impact"><a class="pub-doi" href="{target}">Article →</a></div>'

    title_html = rich_title(str(pub.get("title") or ""))
    authors = rich_authors(str(pub.get("authors") or ""))
    journal = esc(pub.get("journal"))
    citation = esc(pub.get("citation"))
    meta_bits = [authors]
    if journal:
        meta_bits.append(f'<i>{journal}</i>')
    if citation:
        meta_bits.append(citation)
    meta = " · ".join(meta_bits)
    title_tag = f'<a href="{target}">{title_html}</a>' if target else title_html
    tag_text = esc(" ".join(tags))
    tag_block = f'<div class="pub-tags">{label_html}</div>' if label_html else ""
    return f'''<article class="pub-item" data-year="{year}" data-tags="{tag_text}">
<div class="pub-year">{year}</div>
<div class="pub-body"><h2>{title_tag}</h2><p class="pub-meta">{meta}</p>{tag_block}{blog_html}</div>
{impact}</article>'''


def cv_pub(pub: dict) -> str:
    target = pub_target(pub)
    title = rich_title(str(pub.get("title") or ""))
    authors = rich_authors(str(pub.get("authors") or ""))
    journal = esc(pub.get("journal"))
    citation = esc(pub.get("citation"))
    year = esc(pub.get("year"))
    bits = [authors]
    if journal:
        bits.append(f'<i>{journal}</i>')
    if citation:
        bits.append(citation)
    if pub.get("type") == "preprint":
        bits.append("Preprint")
    link = f'<a href="{target}">{title}</a>' if target else title
    return f'<li><span class="cv-pub-year">{year}</span><div><strong>{link}</strong><span>{" · ".join(bits)}</span></div></li>'


def render_publications(data: dict) -> str:
    pubs = data["publications"]
    peer_reviewed = sum(1 for p in pubs if p.get("type") != "preprint")
    years = sorted({int(p["year"]) for p in pubs if p.get("year")}, reverse=True)
    year_buttons = "".join(
        f'<button class="filter-btn" data-filter="{year}" aria-pressed="false">{year}</button>'
        for year in years[:4]
    )
    articles = "\n".join(pub_article(p) for p in pubs)
    generated = esc(data.get("generated") or "")
    return f'''<!doctype html>
<html lang="en-NZ"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Publications — Rhys White</title><meta name="description" content="Publications by microbial genomics scientist Rhys White, with live Altmetric attention badges and ORCID-backed updates.">
<link rel="canonical" href="https://rhyswhite.github.io/publications/"><link rel="icon" href="/assets/img/mark.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/css/site.css"></head><body>
{header('publications')}
<main id="main"><section class="page-hero"><div class="container"><p class="eyebrow">Publications</p><h1>Research record.</h1><p class="lede">{peer_reviewed} peer-reviewed publications across genomic surveillance, antimicrobial resistance, bacterial evolution and implementation. Current preprints are labelled explicitly.</p><div class="source-row"><a href="https://orcid.org/{ORCID}">ORCID</a><span>weekly discovery</span><a href="{SCHOLAR}">Google Scholar</a><span>citation profile</span><span class="source-updated">site data {generated}</span></div></div></section>
<section class="section white"><div class="container">
<div class="filter-bar"><div class="filters" aria-label="Publication filters"><button class="filter-btn" data-filter="all" aria-pressed="true">All</button><button class="filter-btn" data-filter="outbreak" aria-pressed="false">Outbreak genomics</button><button class="filter-btn" data-filter="mobile" aria-pressed="false">AMR &amp; mobile elements</button><button class="filter-btn" data-filter="implementation" aria-pressed="false">Nanopore implementation</button><button class="filter-btn" data-filter="population" aria-pressed="false">Bacterial population genomics</button><button class="filter-btn" data-filter="comparative" aria-pressed="false">Comparative / veterinary genomics</button><button class="filter-btn" data-filter="methods" aria-pressed="false">Methods / software</button>{year_buttons}</div><label><span class="sr-only">Search publications</span><input class="pub-search" type="search" placeholder="Search publications"></label></div>
<div class="pub-list">{articles}</div><p class="pub-empty">No publications match that filter.</p>
<div class="publication-note"><strong>Attention ≠ citations.</strong><span>Altmetric badges show attention to the individual output. Citation profiles remain linked separately through Google Scholar and ORCID.</span></div>
</div></section></main>
{footer()}
<script async src="https://embed.altmetric.com/assets/embed.js"></script><script src="/assets/js/site.js"></script></body></html>'''


def render_cv(data: dict) -> str:
    pubs = data["publications"]
    pub_items = "\n".join(cv_pub(p) for p in pubs)
    return f'''<!doctype html>
<html lang="en-NZ"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CV — Rhys White</title><meta name="description" content="Curriculum vitae of Dr Rhys White, microbial genomics scientist in Aotearoa New Zealand."><link rel="canonical" href="https://rhyswhite.github.io/cv/"><link rel="icon" href="/assets/img/mark.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/css/site.css"></head><body class="cv-page">
{header('cv')}
<main id="main"><section class="cv-hero"><div class="container cv-hero-grid"><div><p class="eyebrow">Curriculum vitae</p><h1>Rhys White <span>PhD, MASM, MRSNZ</span></h1><p>Scientist · Genomics &amp; Bioinformatics · Health Security · New Zealand Institute for Public Health and Forensic Science</p></div><div class="cv-actions"><button class="button primary" type="button" data-print-cv>Print / save PDF</button><a class="button" href="mailto:{EMAIL}">Email</a></div></div></section>
<section class="cv-sheet"><div class="container cv-layout"><aside class="cv-side">
<section><h2>Expertise</h2><p>Applied microbial genomics · AMR and mobile genetic elements · nanopore sequencing implementation · reproducible bioinformatics · genomic epidemiology.</p></section>
<section><h2>Links</h2><div class="cv-links"><a href="https://orcid.org/{ORCID}">ORCID</a><a href="{SCHOLAR}">Google Scholar</a><a href="https://github.com/RhysWhite">GitHub</a><a href="https://www.phfscience.nz/staff-profiles/rhys-white/">PHF Science</a><a href="https://www.linkedin.com/in/rhystwhite/">LinkedIn</a><a href="https://www.researchgate.net/profile/Rhys-White-2">ResearchGate</a><a href="https://bsky.app/profile/rhystwhite.bsky.social">Bluesky</a><a href="https://x.com/RhysTWhite">X</a></div></section>
<section><h2>Research software</h2><p><strong>NEXCISION</strong><br><span>Released · Bioconda</span></p><p><strong>BRANCHSNV</strong><br><span>Alpha research software</span></p></section>
<section><h2>Memberships</h2><p>Royal Society Te Apārangi</p><p>Australian Society for Microbiology</p><p>Microbiology Society</p><p>American Society for Microbiology</p><p>New Zealand Microbiological Society</p></section>
</aside><div class="cv-main">
<section class="cv-section"><h2>Appointments</h2><div class="cv-entry"><time>2022–present</time><div><h3>Scientist, Genomics &amp; Bioinformatics · Health Security</h3><p>New Zealand Institute for Public Health and Forensic Science (PHF Science) · Aotearoa New Zealand</p></div></div><div class="cv-entry"><time>2020–2022</time><div><h3>Senior Research Assistant / Technician</h3><p>The University of Queensland · Australia</p></div></div><div class="cv-entry"><time>2021–2022</time><div><h3>Bioinformatician</h3><p>Centre for Bioinnovation, University of the Sunshine Coast · Australia</p></div></div><div class="cv-entry"><time>2017</time><div><h3>Public Health Intelligence Analyst</h3><p>Public Health Wales · United Kingdom</p></div></div></section>
<section class="cv-section"><h2>Education</h2><div class="cv-entry"><time>2017–2022</time><div><h3>PhD · Microbial Genomics</h3><p>The University of Queensland · Australia</p></div></div><div class="cv-entry"><time>2016</time><div><h3>BSc (Hons) · Biology</h3><p>Cardiff University · United Kingdom</p></div></div></section>
<section class="cv-section"><h2>Leadership &amp; professional service</h2><div class="cv-entry"><time>2026–present</time><div><h3>Editor · <i>Microbial Genomics</i></h3><p>Microbiology Society</p></div></div><div class="cv-entry"><time>2025–present</time><div><h3>Future Leaders Mentor</h3><p>American Society for Microbiology</p></div></div><div class="cv-entry"><time>2025–present</time><div><h3>Co-founder / co-organiser · AMR Research Forum</h3><p>PHF Science–Ministry for Primary Industries</p></div></div><div class="cv-entry"><time>2023–present</time><div><h3>Co-organiser · One Health Aotearoa Symposium</h3></div></div><div class="cv-entry"><time>Professional service</time><div><h3>Peer review, thesis examination and research mentoring</h3><p>Microbial genomics · infectious disease · antimicrobial resistance</p></div></div></section>
<section class="cv-section"><h2>Selected awards</h2><div class="cv-entry"><time>2026</time><div><h3>Queenstown Research Week travel award</h3><p>Queenstown Research Week · Infectious Diseases Aotearoa</p></div></div><div class="cv-entry"><time>2024</time><div><h3>Best ASM Flashstory Award</h3><p>Australian Society for Microbiology</p></div></div><div class="cv-entry"><time>2024</time><div><h3>Queenstown Research Week travel award</h3><p>Queenstown Research Week · Pathogen Genomics</p></div></div><div class="cv-entry"><time>2022</time><div><h3>FEMS Journals Best Poster Prize</h3></div></div><div class="cv-entry"><time>2019–2026</time><div><h3>Oxford Nanopore conference bursaries</h3></div></div></section>
<section class="cv-section cv-publications"><div class="cv-section-head"><h2>Publications &amp; preprints</h2><span>Automatically shared with the Publications page</span></div><ol>{pub_items}</ol></section>
</div></div></section></main>
{footer()}
<script src="/assets/js/site.js"></script></body></html>'''


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
    metrics_data = json.loads(METRICS.read_text(encoding="utf-8")) if METRICS.exists() else {}
    metrics = metrics_data.get("metrics", {})

    blog_lookup = {}
    if BLOG_DATA.exists():
        blog_data = json.loads(BLOG_DATA.read_text(encoding="utf-8"))
        for post in blog_data.get("posts", []):
            if str(post.get("status") or "").strip().lower() != "published":
                continue
            blog_doi = str(post.get("doi") or "").strip().lower()
            blog_slug = str(post.get("slug") or "").strip()
            if blog_doi and blog_slug:
                blog_lookup[blog_doi] = blog_slug

    publications = []
    for original in data.get("publications", []):
        pub = dict(original)
        doi = str(pub.get("doi") or "").strip().lower()
        override = overrides.get(doi, {}) if doi else {}
        if override.get("exclude") is True:
            continue
        if override:
            pub.update({k: v for k, v in override.items() if k != "exclude"})

        metric = metrics.get(doi, {}) if doi else {}
        citations = metric.get("citations")
        if isinstance(citations, int) and citations > 0:
            pub["openalex_citations"] = citations
            pub["openalex_url"] = metric.get("openalex_id", "")

        if doi in blog_lookup:
            pub["blog_slug"] = blog_lookup[doi]

        publications.append(pub)
    data["publications"] = publications
    PUBLICATIONS_OUT.parent.mkdir(parents=True, exist_ok=True)
    CV_OUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLICATIONS_OUT.write_text(render_publications(data), encoding="utf-8")
    CV_OUT.write_text(render_cv(data), encoding="utf-8")
    print(f"Rendered {len(data['publications'])} records into Publications and CV pages.")


if __name__ == "__main__":
    main()
