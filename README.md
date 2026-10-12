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
`nav:` in `mkdocs.yml`.

The site is built in two languages with
[mkdocs-static-i18n](https://ultrabug.github.io/mkdocs-static-i18n/):
English at `/`, French at `/fr/`. `page.md` is the English page and
`page.fr.md` its French translation; a page without a French file is shown in
English on the French site. Link to `page.md` from either language. The French
navigation is the `nav` under the `fr` language in `mkdocs.yml`; keep it in
step with the English `nav:`. `mkdocs build --strict` (run by CI on every push)
fails on a broken link or a page missing from the navigation.

Links to code point at the repositories on GitHub (`djassa-BE`,
`djassa-App-*`, `djassa-Web`, branch `integration`).

## Deploy on Render (behind a login)

The docs hold internal and confidential pages, so the site is not a public
static site: [render.yaml](render.yaml) runs it as a small web service that
asks for one shared login ([server.py](server.py), HTTP basic auth over
HTTPS). Every push to `main` deploys.

1. Render dashboard → **New → Blueprint** → this repository. Render reads
   `render.yaml` and creates **`fidelia-docs`** (Python, free plan, Frankfurt).
2. Once it is live, open the service's **Environment** tab: the login is
   `DOCS_USERNAME` (`fidelia`) and `DOCS_PASSWORD`, which Render generated.
   Change the password there to rotate it; the service restarts with it.
3. Share the address and login only with people allowed to read every page,
   internal ones included.

The free plan sleeps after 15 minutes without a visit and takes about a
minute to wake; set `plan: starter` in `render.yaml` to keep it always on.
The server refuses to start without a password of 16 characters or more.
After 10 wrong logins in 10 minutes, an address is refused for 10 minutes.

Run it locally as on Render:

```bash
mkdocs build --strict
DOCS_PASSWORD=a-local-password-of-16+ python server.py   # http://127.0.0.1:8000
python -m pytest -q tests                                  # the server's tests
```

## Where the documents come from

This repository is the only home of the documentation. It was moved here on
10 October 2026 from `fidelia-BE/docs` (commit `12b9949`), under the same
paths, so a mention like `docs/technical/PRODUCTION.md` in the code or a
commit message points here. Links that left `docs/` were rewritten to GitHub
addresses.

## Sections

| Section | Contents |
|---|---|
| Business | Concept, market, business model, roadmap, KPIs, partners, investor and finance documents (one financial model: `FINANCE.md`) |
| Regulation | Personal data and ARTCI |
| Technical | Technical guide, enrollment, deployment (test, VPS, production), Google Play |

Contact: contact.fidelia@regisse.com
