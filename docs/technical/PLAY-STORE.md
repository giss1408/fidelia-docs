# Publishing the apps on Google Play

Two apps, one Play Console account. Part A is the order to do things in, for
the first release and every one after it; Part B is what the Play forms ask
and how to answer them.

| App | Package (permanent once published) | Repository | Signing key on the release Mac |
|---|---|---|---|
| Fidelia (customers) | `com.regisse.fidelia` | fidelia-App-user | `~/djassa-user-release.jks` |
| Fidelia Pro (merchants) | `com.regisse.fidelia.pro` | fidelia-App-retailer | `~/djassa-merchant-release.jks` |

Both target Android 16 (API 36), which Play requires for new apps and updates
since 31 August 2026. The keys' aliases and passwords live in the team's
password manager (they are also the `ANDROID_*` GitHub secrets). Without a key
and its passwords no update of that app can ever be published: keep a backup.

# Part A — Release steps

## 0. Before the first release (once)

1. **Protect the keys.** `chmod 600 ~/djassa-*-release.jks`. Move the
   passwords from any plain-text file (`~/djassa-*-github-secrets.txt`) into
   the password manager, then delete that file.
2. **Privacy policy**: live at `https://fidelia.milikey-energy.com/confidentialite/` (fidelia-Web
   `public/confidentialite/index.html`, legal entity and address filled in).
   Keep it in line with the ARTCI declaration and check the page loads (§ 8).
3. **Screenshots**: 2 to 8 per app (§ 7).
4. **Decide the server** the build talks to: the repository variable
   `FIDELIA_API_BASE` in each app repository (Settings → Secrets and variables
   → Actions → Variables). Today it is the **test** API: shared test numbers,
   no real SMS, simulated payments. Fine for internal testing; real merchants
   and customers need the production API ([PRODUCTION.md](PRODUCTION.md)).
5. The reviewed build must include account deletion: tag from `integration`
   (or `trunk`) at a version that has it.

## 1. Build the release

From `integration` (test) or `trunk` (production), in each app repository:

```bash
git checkout integration && git pull
git tag vX.Y.Z && git push origin vX.Y.Z      # the next version, e.g. v0.2.1
```

The workflow **Release APKs** builds, signs and publishes:

* the APKs, as a public GitHub Release (the website's `/app/` download page
  serves the latest one);
* the **Play bundle**, as the run's artifact `play-bundle-<version>-<number>`
  (`app-release.aab`, kept 90 days, never public).

Check the run is green in the repository's **Actions** tab. The version code
is the run number, so it always goes up, as Play requires. Locally,
`scripts/build-release.sh <https api>` builds both (needs
`android/key.properties`).

The first Play release can use v0.2.0, already built on 9 October 2026:
[merchant run](https://github.com/giss1408/djassa-App-retailer/actions/runs/37976965256),
[customer run](https://github.com/giss1408/djassa-App-user/actions/runs/37976972377).

## 2. Create each app in Play Console (first release only)

1. **Create app**: name *Fidelia* or *Fidelia Pro*, default language
   **French (France) – fr-FR**, **App**, **Free**. Accept the declarations.
2. **Store presence → Main store listing**: copy from the app repository, as
   in § 7.
3. **Policy → App content**: answer each form as in § 8, including Data
   safety.

## 3. Upload to internal testing

1. Download the bundle: open the release run (Actions tab, signed in to
   GitHub), **Artifacts** → `play-bundle-…`, unzip → `app-release.aab`.
2. Play Console → the app → **Test and release → Testing → Internal testing →
   Create new release**.
3. **App signing (first release only)**: follow § 6.
4. Upload `app-release.aab`.
5. **Release notes** (French): the version's lines from the app's
   `CHANGELOG.md`, shortened to 500 characters, or
   `android/fastlane/metadata/android/fr-FR/changelogs/default.txt`.
6. **Testers**: create an email list (the team), save, and share the opt-in
   link. Testers open it on their phone, accept, then install from Play.
7. **Save → Review release → Start rollout to Internal testing.** Internal
   tests are available within minutes, without Google's review.

## 4. The pilot: closed testing

A personal developer account must run a closed test with **at least 12
testers opted in for 14 consecutive days** before it can publish to
everyone. The pilot is that test:

1. Point `FIDELIA_API_BASE` at the production API and tag a new version.
2. **Testing → Closed testing → Create track** (e.g. *Pilote Abidjan*), upload
   the new bundle, add the pilot merchants, their cashiers and the team as
   testers (email list or Google Group), share the opt-in link on WhatsApp.
3. Closed tests go through Google's review (from a few hours to a few days).
4. After 14 days with 12 or more testers, **Production** unlocks: apply for
   production access in the Dashboard.

## 5. Every later release

1. Add the version's section to the app's `CHANGELOG.md` and update
   `changelogs/default.txt`.
2. Tag the next version (§ 1).
3. Download the new bundle and create a release on the same track (§ 3,
   without the signing part). Use **Promote release** to move a tested build
   from internal to closed testing, or to production.
4. Keep the website APKs and Play on the same version: both come from the
   same tag.

### If something goes wrong

| Problem | Cause and fix |
|---|---|
| Play: *version code already used* | A bundle from an older run. Use the newest run's artifact, or tag a new version. |
| Play: *wrong signing key* | The bundle was signed with another key. It must be signed by the release key in the GitHub secrets; check the run used them (the workflow refuses to build unsigned). |
| Play: *target API level* | Both apps target API 36; a build from before v0.2.0 does not qualify. |
| Testers do not see the app | They must open the opt-in link **with the Google account** on their phone, accept, then search or follow the Play link. |
| Sign-in fails for real users | The build talks to the test API, which sends no SMS. Use a production build (§ 4). |

# Part B — Reference

## 6. Signing: keep one key for Play and the website

The APKs on the website's `/app` page are signed with the release key stored
in the GitHub secrets (`ANDROID_KEYSTORE_BASE64` and friends). Android only
installs an update signed with the same key as the installed app, so:

* In Play Console → the app → **Test and release → App integrity → App
  signing**, choose **Use a different key → Export and upload a key from Java
  keystore**. Play gives a download link for its PEPK tool and a command; run
  it on the release Mac with the matching `.jks` and its alias, and upload the
  `.zip` it writes. Play then signs every install with **our** key, and a
  phone can move between the website APK and the Play version without
  uninstalling.
* If Play generates its own key instead, the two versions cannot update each
  other: a tester must uninstall the website APK (and lose unsynced data)
  before installing from Play.
* The upload key is the same file.

## 7. Store listing

Everything is in each app repository under
`android/fastlane/metadata/android/fr-FR/`:

| Field | File | Limit |
|---|---|---|
| App name | `title.txt` | 30 |
| Short description | `short_description.txt` | 80 |
| Full description | `full_description.txt` | 4000 |
| App icon (512 × 512, 32-bit PNG) | `images/icon.png` | |
| Feature graphic (1024 × 500) | `images/featureGraphic.png` | |
| Phone screenshots, in order | `images/phoneScreenshots/*.png` | 2 to 8 |
| Release notes | `changelogs/default.txt` | 500 |

`scripts/make-icons.py` redraws the icon and feature graphic with the launcher
icons. Screenshots: PNG or JPEG, each side between 320 and 3840 px, the long
side at most twice the short side (a 1080 × 2400 capture must be cropped to
1080 × 2160).

Category: Fidelia → *Shopping*; Fidelia Pro → *Business*. Contact email
(shown publicly): `contact.fidelia@regisse.com`.

## 8. App content (Policy → App content)

| Form | Answer |
|---|---|
| Privacy policy | `https://fidelia.milikey-energy.com/confidentialite/` (fidelia-Web `public/confidentialite/`) |
| App access | Restricted: give reviewers a test number and its code. On the test API, `07 00 00 00 01` (customer) and `07 00 00 00 02` (merchant) sign in with `000000`. |
| Ads | No ads |
| Content rating | Questionnaire: reference / utility app; no violence, sexuality, gambling, drugs; users do not chat. Shops publish photos and deals reviewed by the team. |
| Target audience | 18 and over |
| News app | No |
| Government app | No |
| Financial features | Declare: *payments* (the customer pays the merchant from their own mobile wallet; Fidelia holds no money) and, for layaway, *other*: "paiement d'un produit en plusieurs versements au commerçant, sans crédit, intérêts ni frais". Never describe it as credit or a loan. |
| Health | No |
| Account deletion | `https://fidelia.milikey-energy.com/supprimer-mon-compte/` (fidelia-Web `public/supprimer-mon-compte/`). In the apps: initial → **Compte** → **Supprimer mon compte**. |

Both links are on the custom domain `fidelia.milikey-energy.com` (Cloudflare
CNAME to the fidelia-Web static site on Render), never an `onrender.com` name:
Play shows them to users. The same links serve the App Store (§ 10).

### Data safety

All data goes over HTTPS to Fidelia's own API. No advertising or analytics
SDK. Not sold. Not shared with third parties for their own use (the SMS
provider and Wave act on Fidelia's or the user's behalf, which Play does not
count as sharing).

| Data type | Fidelia (customer) | Fidelia Pro (merchant) | Purpose | Optional? |
|---|---|---|---|---|
| Phone number | Collected | Collected (owner, cashiers, and the customer numbers they enter with consent) | Account management, app functionality | Required |
| Name | No | Collected (contact name on a partner request) | Account management | Required for the request |
| Purchase history | Collected (payments, points, layaway) | Collected (the shop's sales) | App functionality | Required |
| Precise location | No | Collected (the shop's position, when the merchant sets it) | App functionality | Optional |
| Photos and videos | No | Collected (shop photos and videos) | App functionality | Optional |
| App interactions | Collected (screen views, random install id, no phone number) | Collected | Analytics | Required |
| Crash logs, diagnostics | Collected (no phone numbers) | Collected | Analytics, app functionality | Required |

Encrypted in transit: yes. Users can request deletion: yes (§ 9).

The customer app scans QR codes with Google ML Kit, bundled on the phone.
Check ML Kit's own data disclosure page before submitting and add what it
lists (it may report diagnostics to Google).

## 9. Account deletion and privacy policy

* **Customers** delete their account at once in Fidelia (*Compte → Supprimer
  mon compte*): number, points, consent and sessions are erased; the shops'
  sales and payments stay, re-keyed to an anonymous key
  (`app/services/account_delete.py`, `DELETE /api/account`). Refused while a
  layaway plan is open.
* **Merchants, cashiers and field agents** send a request from Fidelia Pro
  (`POST /api/account/deletion-request`). The team handles it in the installer
  (*Suppressions*) within 30 days: for an owner, close the shop or give it a
  new owner first, then *Supprimer le compte*.
* **Without the app**: the public page `/supprimer-mon-compte/` explains both,
  and gives an address to write to.
* The privacy policy at `https://fidelia.milikey-energy.com/confidentialite/` names MILIKEY ENERGY SARLU
  and its address. Keep it in line with the ARTCI declaration
  ([ARTCI.md](../Reglementation/ARTCI.md)).
  The contact address is `contact.fidelia@regisse.com`, forwarded to the
  team's inbox.

## 10. App Store (iOS)

The iOS listings use the same public pages as Google Play.

| App Store Connect field | Value |
|---|---|
| Privacy Policy URL (App Information) | `https://fidelia.milikey-energy.com/confidentialite/` |
| Support URL (version page) | `https://fidelia.milikey-energy.com/` (contact email on the page) |
| Account deletion (guideline 5.1.1(v)) | In the apps: initial → **Compte** → **Supprimer mon compte**; without the app: `https://fidelia.milikey-energy.com/supprimer-mon-compte/` |

App Privacy ("nutrition label"): declare the same data as the Data safety table
(§ 8): phone number, purchase history, and for Fidelia Pro name, precise
location and photos/videos, all *linked to the user*, none used for tracking;
app interactions and crash data *not linked to the user* (random install id).
