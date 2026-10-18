# Personal data and ARTCI: how Fidelia knows who is paying

**Decision (October 2026): Option 1, a phone-verified Fidelia account with explicit consent.** It is implemented in the backend and both apps. This page explains the choice, what the code does, what has been checked against the law, and what is still open for counsel and for ARTCI.

Fidelia never asks for, sees or stores a Wave PIN or Wave credentials. That was never in question; the question was how to link a Wave payment to a customer lawfully.

## 1. The three options

| Option | How it works | Verdict |
|---|---|---|
| **1. Phone-verified account** | The customer signs in to Fidelia with their number and an SMS code, and ticks a consent box. Payments to partner merchants are then matched to that number. | **Chosen.** Consent is given before any processing, by someone who came to Fidelia on their own. |
| 2. Message every payer | Wave's webhook gives Fidelia the payer's number; Fidelia texts them "reply YES to earn points". | Rejected. Fidelia would process the number of someone who has no relationship with it, to send them a commercial message they did not ask for. That conflicts with consent-first processing (Law 2013-450, art. 14) and with the restrictions on unsolicited electronic marketing (Law 2013-546). WhatsApp also requires the recipient's opt-in before a business writes first. Each payment would cost an SMS, for an expected 15–30 % opt-in. |
| 3. Wave in-app integration | The customer authenticates inside Wave, which passes a token to Fidelia. | Not available. Wave gives no persistent customer identifier for this use; it would fall back to the phone number anyway. |

## 2. What the code does

The rule: **no phone number is tied to a sale or to points without a consent on file.** Consents live in one table, `loyalty_consents` (one row per number: source, wording version, date, venue for a counter consent, withdrawal date). Code: `backend-api/app/services/loyalty_consent.py`.

**Where consent is given**

- **Customer app, at sign-in.** An unticked box under the phone field: *"J'accepte que Fidelia garde mon numéro pour relier mes achats chez les commerçants partenaires (y compris mes paiements Wave) et me donner des points. Je peux retirer mon accord à tout moment dans Mon compte."* The app sends the wording version (`fidelite-2026-10`) with the sign-in code. Signing in without ticking it opens the account with no consent. The customer can give it later in *Mon compte*.
- **At the counter, in Fidelia Pro.** When the merchant types a customer's number on a cash sale, a box appears: *"Le client accepte que Fidelia garde son numéro pour ses points"*. The merchant asks the customer aloud and ticks it. The server refuses the sale with that number if there is no consent on file and none given, and says why. A number that already has a consent (from the app or another shop) does not need the box again.

**What happens without consent**

- **Wave payment to the merchant's QR** (`merchant.payment_received`): the sale is recorded for the merchant as confirmed, but **anonymously**. The sender's number is read only to check for a consent and is not stored.
- **Payment from the Fidelia app**: the payment goes through and is the customer's own record, but earns no points.
- **Cash sale at the counter**: recorded without the number. Sales the merchant app queued offline before it asked for consent are sent without the number rather than rejected, so the merchant's books stay complete.

**Withdrawal is erasure.** In *Mon compte*, switching off *Points de fidélité* asks for confirmation, then deletes every point and removes the number from past sales. The sales themselves stay in the merchant's history, anonymous. The consent row is kept, marked withdrawn, as proof of what was done and when.

**Suggestions to the Fidelia team.** An *Aide* (help) entry in the app menu opens WhatsApp to the team's number. It is hidden until the customer has 100 points (merchants and cashiers always have it). The points are not spent. The customer starts the conversation from their own WhatsApp, so it is not unsolicited, but messages then sit in WhatsApp (Meta) and count as personal data Fidelia holds. Declare it with the rest.

**Pilot merchants' self-declared gender.** For the pilot's gender reporting, the team asks each pilot merchant, at the Phase 0 interview, whether they wish to give their gender (woman, man, or prefers not to say). It is optional, stored on the shop's pilot record (`pilot_merchants.owner_gender`), reported only as a count, never used to assess the shop, and cleared when the shop changes owner. Declare it with the rest.

**Favourites and history stay on the phone.** The star on a shop, recent searches and recently viewed shops are saved in a file on the customer's phone, never sent to Fidelia. They work without an account, and *Effacer* or uninstalling the app removes them. Fidelia does not process this data, so it is not part of the declaration.

**Wording changes.** If the consent text changes, bump `CURRENT_VERSION` on the server and `loyaltyConsentVersion` in the customer app together. Each row records the version that person agreed to.

## 3. Checked against the law, and not yet

| Point | Status |
|---|---|
| Processing of personal data needs prior consent of the person (Law 2013-450, art. 14) | Confirmed in secondary sources. This is the basis Fidelia relies on. |
| Every processing must be **declared** to ARTCI before it starts; some need **prior authorisation** (Law 2013-450, art. 7) | Confirmed. Authorisation is required for, among others, biometric data, national ID numbers, and **transfers of personal data to another country** (art. 26). |
| Direct electronic marketing (SMS, email) without a prior relationship is restricted (Law 2013-546 on electronic transactions) | Confirmed in substance. The exact article and the effect of ordinance 2024-950 are for counsel. |
| Sanctions | Up to XOF 10 M for a first breach; up to XOF 100 M or 5 % of turnover for a repeat within 5 years. |
| Previous version of this page citing art. 16 (proportionality) and art. 22 | **Not verified**; those citations were removed. |
| Statements that Djamo, Kippa or Moniepoint work this way | **Not verified**, removed. Kippa and Moniepoint are Nigerian, under a different law. |
| Whether Wave's terms allow a merchant's webhook data (the sender's number) to be shared with Fidelia for loyalty | **Open.** Ask Wave in writing during Phase 0. |

## 4. Hosting: data stays in the EU, with a transfer authorisation

**Decision (October 2026): keep the API and the data on Render in Frankfurt, and ask ARTCI for a transfer authorisation.** Cloudflare sits only in front of Render: it serves the domain (DNS), caches media and static files (CDN) and filters traffic (WAF). It does not run the API or store Fidelia's data.

**Why no host in Côte d'Ivoire for now.** The ARTCI question is **where personal data is stored and processed**, not where it enters the network. None of the providers considered can store data in Côte d'Ivoire:

| Provider | Data location in Côte d'Ivoire | Verdict |
|---|---|---|
| **Render** | No (Frankfurt is the closest region) | **Chosen.** Already set up (`render.production.yaml`, `region: frankfurt`). |
| **DigitalOcean** | No (closest: Frankfurt, Amsterdam, London) | Rejected. Same legal position as Render, with more servers for the team to run. |
| **Cloudflare** | No. Abidjan is an edge location only; its storage products (D1, R2, Workers KV) have no Côte d'Ivoire location | Used in front only. A poor fit as the main host (Celery, ffmpeg, Postgres). |

Every option is a transfer abroad (Law 2013-450, art. 26), so the choice was made on cost and operations. Hosting in Germany helps the request: the law allows a transfer to a country with an equal or higher level of protection, and the GDPR is the strongest case Fidelia can make.

**Processors to list in the filing**

| Processor | What it receives | Country | Safeguards |
|---|---|---|---|
| Render | The API: every request, secrets, application logs | Germany (Frankfurt) | TLS, secrets generated by Render, no PIN or Wave credentials stored |
| Neon | The database: accounts, phone numbers, consents, sales, points | **Check the project's region** (must be an EU region) | Encryption at rest, point-in-time restore, direct endpoint with password |
| Cloudflare R2 | Shop photos and videos | **EU jurisdiction to be set** (see below) | Token limited to the one bucket |
| Cloudflare (DNS, CDN, WAF) | Every request, decrypted at the edge to filter and cache it, so it briefly sees phone numbers and sign-in codes. Stores nothing long-term. | Global network, Abidjan edge | TLS Full (strict) to Render, API routes never cached |
| Grafana Cloud | Metrics and logs (access logs can contain IP addresses) | To confirm with the stack's region | Scrape protected by `METRICS_TOKEN`, minimal logs |
| SMS provider (Africa's Talking) | Phone number and sign-in code | To confirm with the provider | Code expires; never logged in production |
| WhatsApp (Meta) | Suggestions the customer chooses to send | United States / global | The customer starts the conversation |

**R2 jurisdiction.** A bucket's jurisdiction is fixed when the bucket is created. Production uses a bucket created with the EU jurisdiction, and `R2_JURISDICTION=eu` points the API and the worker at its EU endpoint (`backend-api/app/services/media_storage.py`, `render.production.yaml`). Media already in a default-location bucket has to be copied into the EU one.

**When to move to a host in Côte d'Ivoire.** Any of these reopens the decision:

- ARTCI refuses the authorisation, or attaches conditions Fidelia cannot meet.
- Fidelia comes under the BCEAO's rules on payment services (Instruction 001-01-2024), for example by holding or moving money instead of reading Wave payments. Financial regulators expect documented control of where data lives.
- A bank or telecom partner requires local hosting by contract.

The target would then be a colocation data centre in Abidjan or an operator's local cloud, not one of the providers above. The Dockerfile, `k8s/` and `terraform/` keep that move open.

The filing has to list the real data flows. Do not describe the service as hosted in Abidjan: the Abidjan edge is Cloudflare's, and the data is in the EU.

## 5. Phase 0 checklist

- [x] Consent at sign-in (customer app) and at the counter (Fidelia Pro), versioned and stored
- [x] Wave webhook keeps no number without consent
- [x] Withdrawal in the app, with erasure of points and of the number on past sales
- [ ] **Clean up data collected before this change** (see below)
- [ ] Privacy notice in the customer app and on the website: what is collected, why, how long, who receives it, how to withdraw, how to contact Fidelia
- [ ] Retention period for the link between a number and its sales (proposal: as long as the consent is active; anonymous sales kept for the merchant's books)
- [x] Decide the hosting option (§ 4): Render Frankfurt, Cloudflare in front, transfer authorisation
- [ ] Complete the processor table in § 4: Neon region, Grafana Cloud region, SMS provider's country
- [ ] Move shop media to an EU-jurisdiction R2 bucket
- [ ] Ask counsel whether Fidelia, as designed, falls under BCEAO Instruction 001-01-2024
- [ ] File the **déclaration** with ARTCI, plus the **demande d'autorisation de transfert** if any data stays abroad
- [ ] Written answer from Wave on using webhook data for loyalty
- [ ] Counsel review of this page and of the consent wording (budgeted under "Regulatory, privacy and commercial counsel")
- [ ] Set `FIDELIA_SUGGESTIONS_WHATSAPP` in production (until then the suggestions entry stays hidden)

**Data collected before this change.** Before October 2026, the webhook stored points on every Wave payer's number. After migration `0023_loyalty_consents` runs, those rows are still there, and nobody has consented. Review them, then unlink and delete them in one transaction. Back up first; this deletes data:

```sql
-- Numbers with wallet-payment points and no consent on file
SELECT customer_id, SUM(points) FROM loyalty_entries
WHERE reason = 'wallet_payment'
  AND customer_id NOT IN (SELECT customer_id FROM loyalty_consents WHERE withdrawn_at IS NULL)
GROUP BY customer_id;
```

The withdrawal code path (`loyalty_consent.withdraw`) does exactly the erasure needed for each of these numbers.

## Sources

- [CIO Mag: ARTCI, declaration or prior authorisation of personal data processing](https://cio-mag.com/cote-divoire-artci-le-traitement-des-donnees-personnelles-desormais-soumis-a-une-autorisation-prealable)
- [African Legal Factory: personal data protection in Côte d'Ivoire](https://africanlegalfactory.com/2024/01/30/understanding-personal-data-protection-in-cote-divoire/?lang=en)
- [Village Justice: biometrics and personal data, art. 7, 14 and 26 of Law 2013-450](https://www.village-justice.com/articles/biometrie-donnees-personnelles-quelles-exigences-legales-pour-les-entreprises,50642.html)
- [Law 2013-546 on electronic transactions (UNODC)](https://sherloc.unodc.org/cld/uploads/res/document/civ/a/Loi_transactions_electroniques.pdf)
- [Autorité de protection des données: laws](https://www.autoritedeprotection.ci/lois/)
- [DataGuidance: Ivory Coast](https://www.DataGuidance.com/jurisdiction/ivory-coast)
- [EUI data protection database: Côte d'Ivoire, transfers to third countries](https://dti.eui.eu/database/page/392)
- [Digitalmag: BCEAO Instruction 001-01-2024 on payment services](https://digitalmag.ci/instruction-n001-01-2024-bceao-les-fintech-ont-jusquau-31-aout-2025-pour-obtenir-un-agrement-de-la-bceao/)
