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

Copied on 10 October 2026 from `fidelia-BE/docs` (commit `12b9949`), with
the links that left `docs/` rewritten to GitHub addresses.

## Sections

| Section | Contents |
|---|---|
| Business | Concept, market, business model, roadmap, KPIs, partners, investor and finance documents |
| Regulation | Personal data and ARTCI |
| Technical | Technical guide, enrollment, deployment (test, VPS, production), Google Play |
| Planning | Concept review and implementation action plan |
| Concept reviews | External reviews of the concept and its messaging |

Contact: contact.fidelia@regisse.com
