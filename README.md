# Rhys White — personal website

Framework-free GitHub Pages site for `https://rhyswhite.github.io/`.

The site is plain HTML, CSS and a small amount of JavaScript. There is no Jekyll theme, Ruby environment, Node package tree or site-build dependency. GitHub Pages can publish the repository root directly.

## Site structure

- `index.html` — homepage
- `research/index.html` — research programme
- `publications/index.html` — generated publication record + live Altmetric badges
- `software/index.html` — research software + `boast`-backed reach metrics
- `cv/index.html` — generated browser-native CV; **Print / save PDF** uses the browser print engine
- `about/index.html` — short professional profile
- `data/publications.json` — single publication dataset used by both Publications and CV
- `data/publication-overrides.json` — curated topic labels kept separate from bibliographic metadata
- `data/impact/nexcision.json` — last-known-good software reach values shown by the website
- `impact/nexcision.toml` — `boast` manifest for NEXCISION
- `scripts/` — publication/metric update scripts
- `.github/workflows/` — scheduled publication and software-reach refreshes

## Publish with GitHub Pages

In the GitHub repository:

1. Open **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select the default branch and `/ (root)`.
4. Save.

The committed `.nojekyll` file ensures GitHub serves the static files directly.

## Automatic publications: ORCID → site

`publications/index.html` and the publication section of `cv/index.html` are generated from the same `data/publications.json` file.

`.github/workflows/publications-sync.yml` runs weekly. It:

1. reads public DOI-bearing works from ORCID `0000-0001-6620-758X`;
2. enriches DOI metadata with Crossref when available;
3. merges curated local topic labels;
4. preserves the previous data if a provider is unavailable;
5. re-renders both Publications and CV;
6. commits only if something changed.

### One-time ORCID setup

The supported ORCID Public API uses a read-only `/read-public` access token. Register a Public API client in ORCID, then add `ORCID_CLIENT_ID` and `ORCID_CLIENT_SECRET` under **Settings → Secrets and variables → Actions**. The workflow obtains the long-lived read-public token automatically.

Alternatively, if you already have a `/read-public` token, add it as `ORCID_ACCESS_TOKEN`.

After that, publication discovery is automatic. To test it immediately, open **Actions → Refresh publications → Run workflow**.

Curated publications without a DOI are retained locally during ORCID refreshes, so a legitimate non-DOI article cannot disappear simply because ORCID discovery is DOI-based.

### Curating publication topics

Bibliographic metadata is automated; scientific categorisation is not delegated to an API.

Edit `data/publication-overrides.json` to assign site filters and compact labels to a DOI. The public filters are deliberately scientific rather than bibliometric: **Outbreak genomics**, **AMR & mobile elements**, **Nanopore implementation**, **Bacterial population genomics**, **Comparative / veterinary genomics**, and **Methods / software**. Publications can belong to more than one theme. New ORCID works without an override receive conservative title-based tags until you curate them. Use `"exclude": true` for a DOI that should remain in ORCID but not appear on the website.

Run locally after changing data:

```bash
python scripts/render_publications.py
```

## Altmetric

The Publications page uses Altmetric's official DOI badge embed. Badges are live and hide themselves when an output has no tracked mentions. Scores are **not** copied into the repository, so they cannot become stale.

No Altmetric API key is required for those visible badges.

An optional `ALTMETRIC_KEY` repository secret can also be supplied to `boast` if you have access to an Altmetric Details Page API key. That is separate from the public badge embed.

## Research-software reach with `boast`

`.github/workflows/impact-snapshot.yml` runs monthly for NEXCISION using `impact/nexcision.toml`.

It tracks the linked project across:

- GitHub — stars and release downloads
- Bioconda — package downloads
- scholarly providers — citation/attention measures supported by `boast`
- Altmetric — only when `ALTMETRIC_KEY` is available

The workflow commits the raw timestamped `boast` snapshots in `impact/snapshots/` and converts the newest usable values into `data/impact/nexcision.json` for the site.

Provider failures do not blank the public website. The last valid committed metrics remain visible, while the failed Action still turns red so the problem is not hidden.

The workflow currently pins `boast` to `0.5.0`; update `BOAST_VERSION` deliberately when adopting a newer release.

To initialise metrics immediately, open **Actions → Research software reach → Run workflow**.

## Google Scholar

Google Scholar remains prominently linked as the citation-profile destination. The site does not scrape Scholar: there is no supported public Google Scholar API suitable for a maintainable publication sync.

## Updating core content

The main narrative pages remain intentionally hand-curated:

- `index.html`
- `research/index.html`
- `software/index.html`
- `about/index.html`

This keeps scientific claims deliberate while allowing bibliographic and reach data to update automatically.

## Portrait

Replace `assets/img/rhys-white.jpg` with a new image using the same filename to update the portrait everywhere it is used.

## Website provenance

The current website was rebuilt in 2026 as a framework-free static site using bespoke HTML, CSS, JavaScript and Python tooling. The repository previously used an Academic Pages/Minimal Mistakes-derived site; a repository provenance audit found no substantial retained code or code assets from that theme in the current implementation.

External services and tools used by the current site include GitHub Pages, ORCID, OpenAlex, Altmetric and `boast`. Relevant acknowledgements are provided on the website and in the repository where appropriate.
