# Fidelia — documentation

Business, regulation and technical documentation of Fidelia, published as a
site with [MkDocs](https://www.mkdocs.org/) and the Material theme.

## Read and edit locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
mkdocs serve            # http://127.0.0.1:8000, reloads on every save
```

Pages are Markdown files in `docs/`. A new page must also be listed under
`nav:` in `mkdocs.yml`. `mkdocs build --strict` (run by CI on every push)
fails on a broken link or a page missing from the navigation.

Links to code point at the repositories on GitHub (`djassa-BE`,
`djassa-App-*`, `djassa-Web`, branch `integration`).

## Where the documents come from

This repository is the only home of the documentation. It was moved here on
10 October 2026 from `fidelia-BE/docs` (commit `12b9949`), under the same
paths, so a mention like `docs/technical/PRODUCTION.md` in the code or a
commit message points here. Links that left `docs/` were rewritten to GitHub
addresses.

## Sections

| Section | Contents |
|---|---|
| Business | Concept, market, business model, roadmap, KPIs, partners, investor and finance documents |
| Regulation | Personal data and ARTCI |
| Technical | Technical guide, enrollment, deployment (test, VPS, production), Google Play |
| Planning | Concept review and implementation action plan |
| Concept reviews | External reviews of the concept and its messaging |

Contact: contact.fidelia@regisse.com
