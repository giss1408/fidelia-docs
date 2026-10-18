# Production: going live and staying watched

Production is the pilot with real merchants, real phone numbers and real
Wave payments. It runs from [`render.production.yaml`](https://github.com/giss1408/djassa-BE/blob/integration/render.production.yaml),
separate from the test environment in `render.yaml` (shared test numbers,
simulated payments, free plan). The two never share a database.

```
phone ──► Cloudflare (DNS, WAF, cache; Abidjan edge)
            ├─ api.<domain>   ──► fidelia-api-prod (Render, Frankfurt, 2 instances)
            │                       ├─► Neon (Postgres, EU)
            │                       ├─► fidelia-kv-prod (rate limits, video queue)
            │                       └─► R2 (media, EU) ◄── fidelia-worker-prod (videos)
            └─ media.<domain> ──► R2 (photos and videos, cached at the edge)
fidelia-metrics-prod (private) scrapes each API instance ──► Grafana Cloud
```

Everything runs the one Docker image in `backend-api/Dockerfile`: the API,
the worker, the test environment and CI.

What watches it:

| Question | Where the answer is | Alerts you |
|---|---|---|
| Is the API up and reaching its database? | Uptime monitor on `/ready` | SMS / WhatsApp / email within 2 minutes |
| Are requests failing or slow? | Grafana Cloud: *Fidelia API overview* | `HighErrorRate`, `SlowRequests` |
| Are payments being confirmed? | Grafana Cloud: *Webhooks overview* | `PaymentWebhookFailing` |
| Can people sign in? Is someone burning SMS? | Grafana Cloud: *Fidelia apps and sign-in* | `OtpDeliveryFailing`, `OtpSentButNotVerified`, `OtpDailyBudgetReached` |
| Are the apps crashing? | Same dashboard; stacks in the installer site (*Erreurs des apps*) | `AppErrorSpike`, `AppCrashAfterRelease` |
| Is the pilot being used? | Grafana Cloud: *Fidelia pilot usage*; `GET /api/admin/usage` | — |
| What happened at 14:02? | Log service, searched by `request_id` or route | — |

## 1. Accounts to open (once)

1. **Render**: a paid workspace. The Blueprint creates the API (two Starter
   instances), the video worker, a Key Value store and the metrics scraper
   (Starter each), and the installer site (static).
2. **Neon**: the production project on a paid plan, with point-in-time
   restore. See § Database.
3. **SMS for sign-in codes**:
   * **Orange Developer** (main): an app subscribed to *SMS Côte d'Ivoire*,
     an SMS bundle bought in *My Apps*, and the sender name `FIDELIA`
     requested through Orange's web form (5 working days, 15 for MTN;
     codes go out under Orange's default sender until then). In the same
     form, the **notification URL** for delivery receipts:
     `https://api.<domain>/webhooks/orange/sms-dr/<ORANGE_DR_TOKEN>`. Orange
     whitelists it before sending receipts; it must be the Cloudflare
     address (HTTPS on 443, a CA-signed certificate), never onrender.com.
   * **Africa's Talking** (fallback): production account with credit, and
     the `FIDELIA` sender ID applied for. It sends the code whenever Orange
     fails.
4. **Cloudflare**: the domain (its DNS moved to Cloudflare), and an R2 bucket
   `fidelia-media-prod` **created with the EU jurisdiction** (it cannot be
   changed later), with an API token limited to it.
5. **Grafana Cloud**: free tier is enough for the pilot (metrics, dashboards,
   alerting).
6. **Better Stack** (or UptimeRobot): uptime monitors, and log storage if
   Render's own retention is too short for you.

## 2. Deploy

1. Render → **New → Blueprint** → the `fidelia-BE` repository, Blueprint path
   `render.production.yaml`. Render asks for every `sync: false` value; fill
   them from the table in § 7. `DATABASE_URL` and the `R2_*` values are
   asked twice, for the API and for the worker: enter the same ones.
2. Production follows the `trunk` branch (the test environment follows
   `integration`). The API deploys with `autoDeploy: false`: a merge into
   `trunk` does not reach real merchants until someone presses **Manual
   Deploy**. Migrations run in
   the pre-deploy step; if one fails, the previous build keeps serving.
3. Put Cloudflare in front (§ 3). Until then the API answers 403 to
   everything but `/health`: it accepts only requests that came through
   Cloudflare.
4. Copy `https://api.<domain>` into the installer site's
   `VITE_FIDELIA_API_BASE`, and the installer site's address into the API's
   `CORS_ORIGINS`. Redeploy both.
5. Check: `https://api.<domain>/health` → `{"status":"ok"}`, `/ready` →
   `{"ready":true}`, `/metrics` → **404**, and the onrender.com address →
   **403** on `/api/categories`.
6. Build the apps for production: `scripts/build-release.sh https://api.<domain>`
   in each app repository. Test builds keep pointing at the test API.

The API refuses to start in production with a test-only setting: a console
SMS sender, `TEST_OTP_NUMBERS`, simulated payments, local media storage, a
missing encryption key, no `CLOUDFLARE_ORIGIN_SECRET`, or no
`RATE_LIMIT_STORAGE_URI`. A failed start in the deploy log names the setting.

## 3. Cloudflare in front

Cloudflare answers for the domain, filters traffic and caches media at its
Abidjan edge. It does not run the API or store its data.

Steps 1 to 8 are applied by Terraform:
[`terraform/cloudflare`](https://github.com/giss1408/djassa-BE/tree/integration/terraform/cloudflare)
(its README has the token permissions and the commands). Prefer it to the
dashboard: the settings are reviewed, repeatable, and nobody forgets one. Only
two things stay manual: Bot Fight Mode off, and switching the API record to
Proxied once Render has verified the domain (a one-line change there). The
same settings, in the Cloudflare dashboard for the domain:

1. **API hostname.** Render → fidelia-api-prod → *Settings* → *Custom
   Domains* → `api.<domain>`. In Cloudflare *DNS*, the CNAME Render asks for
   (`api` → `fidelia-api-prod.onrender.com`), **DNS only** (grey cloud)
   until Render shows the domain verified with a certificate, then
   **Proxied** (orange cloud).
2. **TLS.** *SSL/TLS* → **Full (strict)**. *Edge Certificates* → *Always Use
   HTTPS* on, minimum TLS 1.2.
3. **Origin secret.** *Rules* → *Transform Rules* → *Modify Request Header* →
   new rule "Fidelia origin secret": when *Hostname* equals `api.<domain>`,
   **Set static** `X-Origin-Auth` = the API's `CLOUDFLARE_ORIGIN_SECRET`
   (Render → fidelia-api-prod → Environment). *Set* replaces anything a
   caller sends. Without this rule every request gets 403.
4. **No cache for the API.** *Caching* → *Cache Rules* → when *Hostname*
   equals `api.<domain>` → **Bypass cache**. API answers are personal.
5. **Media hostname.** R2 → `fidelia-media-prod` → *Settings* → *Custom
   Domains* → `media.<domain>`; then `MEDIA_PUBLIC_BASE_URL` =
   `https://media.<domain>` on the API and the worker. Files are written
   once with a one-year immutable cache, so Cloudflare serves repeat views
   from Abidjan.
6. **Staged originals stay private.** Videos wait under `incoming/` for the
   worker, untouched (GPS included), for minutes. R2 → the bucket →
   *Settings* → *Object lifecycle rules*: delete prefix `incoming/` after
   1 day. *Security* → *WAF* → *Custom rules*: when *Hostname* equals
   `media.<domain>` and *URI Path* starts with `/incoming/` → **Block**.
7. **Provider callbacks pass.** *Custom rules*: when *URI Path* starts with
   `/webhooks/wave/` or `/webhooks/orange/`, or equals
   `/api/webhooks/mobile-money` → **Skip** (all
   remaining custom rules, rate limiting, managed rules). Leave **Bot Fight
   Mode off**: on the Free plan it cannot be skipped per path, and it would
   challenge Wave's servers, so payments would stop arriving. Those routes
   are protected by their own token and signature.
8. **Sign-in codes at the edge.** *Security* → *WAF* → *Rate limiting rules*:
   when *URI Path* equals `/api/auth/otp/request`, 5 requests per 10 seconds
   per IP → **Block** for 10 seconds. A second layer in front of the API's own
   limits and the daily SMS budget.
9. **Check.** `curl -s -o /dev/null -w '%{http_code}' https://fidelia-api-prod.onrender.com/api/categories`
   → `403`; the same on `https://api.<domain>` → `200`. Send a test Wave
   payment and see it confirmed.

To rotate the origin secret: set `new,old` in `CLOUDFLARE_ORIGIN_SECRET`
and deploy, change the Transform Rule to `new`, then set `new` alone.

## 4. Metrics and alerts (Grafana Cloud)

The API exports Prometheus metrics at `/metrics`, labelled by route template
(`/api/venues/{venue_id}`, never a raw URL) to keep the series count small.
In production the endpoint answers only with `METRICS_TOKEN`.

1. **Metrics reach Grafana Cloud** through `fidelia-metrics-prod`, a Grafana
   Alloy private service ([`monitoring/alloy/config.alloy`](https://github.com/giss1408/djassa-BE/blob/integration/monitoring/alloy/config.alloy)).
   Each API instance keeps its own counters and the public address reaches
   one at random, so Alloy finds every instance on Render's private network
   (`fidelia-api-prod-discovery`) and scrapes each one with `METRICS_TOKEN`.
   Grafana Cloud → your stack → *Prometheus* → *Send metrics* gives the
   three values the Blueprint asks for: `GRAFANA_REMOTE_WRITE_URL`,
   `GRAFANA_REMOTE_WRITE_USERNAME` (the instance ID) and
   `GRAFANA_REMOTE_WRITE_TOKEN` (an access policy token with `metrics:write`).

   Within two minutes `fidelia_build_info` appears in *Explore*, once per
   instance (two `instance` labels). If an old *Metrics Endpoint* scrape job
   of the public URL exists, delete it: it would count one instance twice.
2. **Dashboards.** *Dashboards → New → Import*, once per file in
   [`monitoring/grafana/dashboards/`](https://github.com/giss1408/djassa-BE/tree/integration/monitoring/grafana/dashboards):
   `api-overview.json`, `apps-and-auth.json`, `pilot-usage.json`,
   `webhooks-overview.json`. Pick the Grafana Cloud Prometheus data source.
   Each has a fixed uid, so importing a newer version replaces the old one.
3. **Alert rules.** [`monitoring/rules/alerts.yml`](https://github.com/giss1408/djassa-BE/blob/integration/monitoring/rules/alerts.yml)
   is the same file the local Prometheus uses. Load it into Grafana Cloud's
   Prometheus with `mimirtool` (credentials from *Grafana Cloud → your stack →
   Prometheus → Details*; the key needs the `rules:write` scope):

   ```bash
   mimirtool rules load monitoring/rules/alerts.yml \
     --address=https://<prometheus host from Details> \
     --id=<Prometheus instance ID> --key=<access policy token>
   ```

   Run it again after every change to the file. The rules then show under
   *Alerting → Alert rules* (data-source managed).
4. **Who gets told.** *Alerting → Contact points*: add at least two people,
   by email and by a channel someone reads at night (Grafana's mobile app, or
   a Telegram or Slack integration). *Notification policies*: `severity =
   critical` → everyone, repeat every 1 h; `warning` → email, repeat every 4 h.
5. **Test the path once**: set `OTP_DAILY_SMS_BUDGET` to `1` for five minutes,
   request two codes, check `OtpDailyBudgetReached` reaches everyone, then put
   the budget back.

## 5. Uptime monitors

Grafana alerts only when metrics arrive. An outside monitor catches the
cases where nothing arrives at all (`ApiMetricsMissing` is the backstop).

| Monitor | URL | Every | Expect |
|---|---|---|---|
| API and database | `https://api.<domain>/ready` | 1 min | 200 and `"ready":true` |
| Installer site | `https://<installer>/` | 5 min | 200 |
| Test download page | `https://<fidelia-web>/app/` | 5 min | 200 |

Alert after 2 failed checks, to the same people as critical alerts.

## 6. Logs

The API writes one JSON line per request (`LOG_FORMAT=json`):

```json
{"ts": "2026-10-04T14:02:11", "level": "info", "logger": "fidelia.access",
 "msg": "POST /api/sales 201 84ms", "request_id": "9f2c…", "method": "POST",
 "route": "/api/sales", "status": 201, "duration_ms": 84.2}
```

5xx lines are `level: error`. Query strings, IPs and bodies are never logged:
query strings carry phone numbers. Every response carries `X-Request-ID`; an
app or a merchant's screenshot can quote it to find the exact line.

The worker's lines are Celery's own (`fidelia-worker-prod` → *Logs*): one
per video job, with its outcome.

Render keeps logs for a limited time. To keep them longer, Render →
*Workspace settings* → **Log Streams** → the syslog endpoint your log service
gives (Better Stack: *Sources → Render*). Keep 30 days at least.

## 7. Settings (keep this table current)

Values set by hand in the Render dashboard do not follow the Blueprint
afterwards. Whenever one changes there, change it here too.

| Setting | Where it comes from | Notes |
|---|---|---|
| `DATABASE_URL` | Neon, production project, direct endpoint | Never the test database. API and worker |
| `FIDELIA_SECRET_KEY` | Generated by Render | Rotating it signs everyone out |
| `FIDELIA_ENCRYPTION_KEY` | Generated by Render | **Copy to the password manager.** Lost or changed: every merchant reconnects Wave |
| `MOBILE_MONEY_SECRETS` | Payment provider's webhook secret | `current,previous` while rotating |
| `OTP_SENDER` | Blueprint: `orange,africastalking` | Tried in that order |
| `ORANGE_CLIENT_ID`, `ORANGE_CLIENT_SECRET` | Orange Developer → My Apps → the app | |
| `ORANGE_SENDER_NAME` | Once Orange confirms it by email | Empty until then; a wrong value stops the start |
| `ORANGE_DR_TOKEN` | `openssl rand -hex 32` | In the notification URL given to Orange; changing it means a new URL through Orange's form |
| `AT_USERNAME`, `AT_API_KEY` | Africa's Talking, production app | |
| `AT_SENDER_ID` | Africa's Talking, once approved | Empty until then |
| `OTP_DAILY_SMS_BUDGET` | Blueprint: 300 | A few times a normal day; raise as the pilot grows |
| `R2_*` | Cloudflare R2 | Bucket `fidelia-media-prod`, `R2_JURISDICTION=eu`. API and worker |
| `MEDIA_PUBLIC_BASE_URL` | `https://media.<domain>` (§ 3) | API and worker |
| `MEDIA_PROCESSING` | Blueprint: `worker` | Videos converted by fidelia-worker-prod |
| `CLOUDFLARE_ORIGIN_SECRET` | Generated by Render | Same value in the Cloudflare Transform Rule (§ 3) |
| `RATE_LIMIT_STORAGE_URI`, `CELERY_BROKER_URL` | Blueprint: fidelia-kv-prod | Set by Render from the Key Value store |
| `CORS_ORIGINS` | The installer site's exact address | Add the public site's domain once it has one |
| `METRICS_TOKEN` | Generated by Render | fidelia-metrics-prod reads it from the API; rotating it needs a redeploy of both |
| `GRAFANA_REMOTE_WRITE_*` (metrics scraper) | Grafana Cloud → Prometheus → Send metrics | |
| `VITE_FIDELIA_API_BASE` (installer site) | `https://api.<domain>` | Never the onrender.com address. Rebuild the site after a change |

## 8. When an alert fires

| Alert | First look | Likely causes and fixes |
|---|---|---|
| **Uptime /ready down** | Render → fidelia-api-prod → Events and Logs | Deploy failed to start (the log names the bad setting); Neon down or out of compute: check Neon status; roll back with *Rollback* on the last good deploy |
| **ApiMetricsMissing** | Is the uptime monitor also red? | Both red: the API is down, see above. Only this one: fidelia-metrics-prod → Logs (scrape refused after a `METRICS_TOKEN` change: redeploy it; remote write refused: the Grafana token) |
| **Every request 403** | Cloudflare → *Rules* → Transform Rules | The origin-secret rule was edited or disabled, or `CLOUDFLARE_ORIGIN_SECRET` changed without the rule |
| **HighErrorRate** | *API overview* → *Errors by route*; logs filtered on `level: error` | One route: a bug, often from the last deploy (*Running build* panel), so roll back. All routes: the database |
| **SlowRequests** | *Latency p95, slowest routes* | Database under load (Neon dashboard); one slow route: a missing index |
| **PaymentWebhookFailing** | Logs on route `/api/webhooks/mobile-money` | 401: the provider rotated its secret, so update `MOBILE_MONEY_SECRETS`; 5xx: a bug, payments are not being confirmed, so treat as urgent and tell affected merchants |
| **OtpDeliveryFailing** | API logs on `fidelia.otp`; Orange *My Apps* balance; Africa's Talking dashboard | Both providers failing: credit spent on both, sender name rejected, outage. Nobody new can sign in meanwhile |
| **OtpSmsNotDelivered** | *Fidelia apps and sign-in*; which `network` | Orange accepts the codes but that network does not deliver them (Orange's known MTN issue). Report it through Orange's form; if it lasts, put `africastalking` first in `OTP_SENDER` |
| **OtpPrimaryProviderFailing** | Orange *My Apps* → the app → balance; API logs `Orange SMS refused` | Bundle spent or expired: buy one. A 400: `ORANGE_SENDER_NAME` not whitelisted, empty it. Codes still go out through Africa's Talking meanwhile |
| **OtpSentButNotVerified** | *Fidelia apps and sign-in* → codes by result | SMS pumping: lower `OTP_DAILY_SMS_BUDGET`, check the provider's per-country spend. Or codes are not arriving: send one to your own phone |
| **OtpDailyBudgetReached** | Same dashboard | Real growth: raise the budget. An attack: keep it, it is doing its job, and look at the per-IP limits |
| **AppErrorSpike / AppCrashAfterRelease** | Installer site → *Erreurs des apps* | A bad release: stop sharing the new APK, fix, release the next tag |

Videos stuck on `processing` for over 30 minutes show as failed to the
merchant. Look at fidelia-worker-prod → Logs: not running (restart it), or
R2 or the database unreachable. If the queue itself is down, the API converts
videos itself, slowly.

After any incident a merchant noticed: write down what happened, when, what
fixed it, and what would have caught it sooner.

## Instances

The API runs two instances. Nothing either one keeps matters to the other:
sessions are tokens, rate-limit counters are in fidelia-kv-prod, the daily
SMS budget is counted in the database, media is in R2, videos go through the
queue. Metrics are per instance and summed by the dashboards and alerts.
More instances: raise `numInstances`; nothing else changes.

## Database

To be completed with the replica plan. Until then the minimum:

* Neon paid plan with point-in-time restore over at least 7 days.
* Region **AWS Europe (Frankfurt)**, next to the API and inside the EU (the
  ARTCI transfer filing names it). Neon cannot move a project to another
  region: check it when creating the project.
* Production compute with **scale to zero off** (*Branches* → `main` →
  *Compute* → *Edit*). Otherwise the first request after a quiet spell waits
  for the database to wake, and `/ready` flaps at night.
* Restore tested once into a scratch branch, and the time it took noted here.
* The production `DATABASE_URL` known only to Render and the password manager.
