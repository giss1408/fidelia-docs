# Fidelia Documentation

> **Fidelia turns everyday sales at neighbourhood shops into proof: a verified business history that the merchant owns and, with consent, can take to a licensed lender.**

*This site is in English and French: use the language menu at the top. The investor brief, investor readiness, finance and letters of interest exist in both languages; the Fin'ELLE proposal is in French only; other pages are in English on both sites.*

## Business: what Fidelia is and why it will work

| Document | Answers |
|---|---|
| [Concept](business/CONCEPT.md) | What Fidelia is, the one-habit idea, the four products, how money moves, identity, the financial-inclusion path, **how to explain it to each audience**, red lines. *Start here.* |
| [Market](business/MARKET.md) | Sourced figures, regulation (BCEAO, PI-SPI, ARTCI), competitive landscape and positioning, tontine and SME finance evidence. |
| [Business model](business/BUSINESS-MODEL.md) | Who pays, revenue streams in order, pricing experiment, unit economics, decision gates. |
| [Roadmap](business/ROADMAP.md) | Where we stand today, phases 0–6 with exit gates, strategic horizon. |
| [KPIs](business/KPI.md) | The North Star, the scorecard per phase, how each KPI is computed and where the data lives, targets, external benchmarks, measurement gaps. |
| [Partners](business/PARTNERS.md) | Institution directory, contact order, acquisition channels, meeting kit, guardrails. |
| [Investor brief](business/INVESTOR-BRIEF.md) | The summary for investors: opportunity, product, traction, market, model, competition, three-year forecast, team, the ask (a XOF 31M pilot round in two tranches), return and risks. *Company details and team track records still to fill before sending.* |
| [Investor readiness](business/INVESTOR-READINESS.md) | Internal: what investors and a crowdfunding campaign will look for and not find yet, the rewritten story, market sizing, competitors and next steps. |
| [Finance](business/FINANCE.md) | The single financial model: itemized six-month pilot budget (XOF 30.82M), three-year forecast and its assumptions, tranche release gates, supplier-quote and evidence registers. The investor brief's numbers come from here. |
| [Fin'ELLE pilot proposal](fr/business/PROPOSITION-PILOTE-FINELLE/) (French only) | Draft proposal to Fin'ELLE: a free six-month pilot where 10–20 of its merchant clients use Fidelia and, with their consent, share a signed sales statement, with the price of the paid follow-on signed at month 3 (conditional commitment template in annex); safeguards, timeline, success measures. *Placeholders to fill and an internal note to remove before sending.* |
| [Letters of interest](business/LETTERS-OF-INTEREST.md) | Non-binding templates for a pilot merchant and an MFI to sign. The French version is the one to sign. |

## Technical: how it is built and run

| Document | Answers |
|---|---|
| [Technical guide](technical/TECHNICAL-GUIDE.md) | Repository map, local development, sync, payments, identity API, configuration, production gaps. |
| [User enrollment](technical/ENROLLMENT.md) | Who can sign in to which app: customers, merchants, cashiers, field agents, admins; the approval checklist, recovery, test accounts, API. |
| [Test deployment (free)](technical/DEPLOY-TEST.md) | API on Render free + Neon, signed APKs on GitHub Releases, the WhatsApp install link, Firebase App Distribution. |
| [VPS test server](technical/VPS-TEST-SERVER.md) | Ubuntu VPS setup and automated test deployment. |
| [Production](technical/PRODUCTION.md) | Going live on Render's paid plan: deploy, settings, Grafana Cloud metrics and alerts, uptime monitors, logs, what to do when an alert fires. |
| [Google Play](technical/PLAY-STORE.md) | Release steps (build, internal and closed testing, later releases) and the Play forms: signing, store listing, app content, Data safety, account deletion. |
| [Architecture](https://github.com/giss1408/djassa-BE/blob/integration/Architecture/README.md) | Topology, application and container security, secrets, Kubernetes. |
| [Contributing](https://github.com/giss1408/djassa-BE/blob/integration/CONTRIBUTING.md) | Branches, tests, security checklist, pull requests. |
| [Monitoring alerts](https://github.com/giss1408/djassa-BE/blob/integration/monitoring/ALERTS.md) | Operational thresholds and access rules. |

App-specific docs live with each app: [merchant app architecture](https://github.com/giss1408/djassa-App-retailer/blob/integration/ARCHITECTURE.md), [public site](https://github.com/giss1408/djassa-Web/blob/integration/README.md).

## Reading paths by audience

| You are… | Read |
|---|---|
| **A merchant or user-facing team member** | Concept §§ 3–6 and § 9 |
| **An investor** | Investor brief first; then Concept → Market → Business model → Roadmap → Finance |
| **An institution or regulator** | Concept §§ 6–8 and § 11 → Market § 4 → Roadmap |
| **A financial or payment partner** | Concept §§ 3, 6 and 9 → Business model → Partners |
| **A developer** | Concept → Roadmap § Where we stand → Technical guide |

## Keeping documents in sync

- These business documents are the **source of truth**. The public site copy (`fidelia-Web/src/content/fr.js` and `en.js`) and app wording must follow them.
- A bilingual page is two files, `page.md` (English) and `page.fr.md` (French), and both change together. Link to `page.md` from either language; the site serves the right one. Adding a French page only needs the `.fr.md` file, plus an entry in the French `nav` in `mkdocs.yml`.
- The roadmap's "Where we stand" table must be updated when a capability ships or a gate is passed.
- Market figures always carry their source and must be re-verified before external or contractual use.
- The original French research and the "Dkassa" instruction notes were consolidated into these documents on 30 September 2026. The originals remain in git history.
- On 12 October 2026 the documentation was cleaned up: the budget and finance-validation packs were merged into `FINANCE.md` (one financial model); the two Google Play guides into `PLAY-STORE.md`; the 29 September concept review and action plan (done or superseded; open items moved to the roadmap), the two external concept reviews and the obsolete investor-room setup were removed. All remain in git history.
