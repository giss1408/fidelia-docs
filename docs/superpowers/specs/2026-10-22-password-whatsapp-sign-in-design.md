# Password sign-in, WhatsApp number checks and the Fidelia Admin app

Date: 2026-10-22 · Status: design, awaiting review

## Goal

Remove every SMS code from Fidelia. People sign in with their phone number and
a password. The team proves each number once by sending a code from its own
WhatsApp, through a new admin mobile app, Fidelia Admin, modelled on
Flariane's `admin_app`. This must ship before the first Google Play release
(v0.3.0 of Fidelia and Fidelia Pro).

**Decided with the owner**

* Model: phone + password; a one-time number check by a WhatsApp code that a
  team member sends by hand (Flariane's model).
* Every account moves: customers, merchants, cashiers, agents and admins.
  No SMS remains anywhere, including the Orange SMS integration.
* The admin app covers accounts only. Shops, media, sign-up requests, lost
  numbers and error reports stay in the web admin, fidelia-installer.

**Success:** a new customer signs up, a team member sends the code from
Fidelia Admin in under a minute, the customer enters it and sees their points;
no request to an SMS provider exists in the code.

## 1. How codes reach people

The API builds the message and returns a `https://wa.me/<number>?text=<message>`
link; the admin app opens it, WhatsApp shows the message already written on the
admin's phone, the admin taps Send. Free, no Meta approval, fits pilot volumes.

All sending goes through one function, `whatsapp_link(e164, message)` in
`app/services/whatsapp.py`, so moving later to the WhatsApp Cloud API (automatic
sending, needs Meta verification and an approved `fr` template) changes only
that function.

Messages (French):

* Code: « Bonjour, voici votre code Fidelia : 482 913. Saisissez-le dans
  l'application. Valable 24 h. Ne le partagez avec personne. »
* Temporary password: « Bonjour, votre mot de passe temporaire Fidelia :
  K7m-29xQ. Vous devrez en choisir un nouveau à la connexion. »

## 2. Accounts and sign-in (fidelia-BE)

### Data

`users` gains:

| Column | Meaning |
|---|---|
| `password_hash` | argon2id (`argon2-cffi`), null until the person sets one |
| `must_change_password` | true after a temporary password; every route but `POST /api/auth/password` answers 403 `password_change_required` |
| `phone_verified_at` | null until the WhatsApp code is entered (or a temporary password sent on WhatsApp is used) |
| `failed_logins`, `locked_until` | wrong-password lockout |

New table `account_checks` (replaces `otp_challenges`, which is dropped):
`id, user_id, kind ("verify_number" | "reset_password" | "change_number"),
new_phone_e164 (change_number only), status ("pending" | "sent" | "done" |
"refused"), secret_hash (HMAC of the code or temporary password), attempts,
expires_at (24 h after sending), sent_by, sent_at, created_at, done_at`.
One open check per user and kind; asking again reuses it.

New table `admin_actions`: `id, admin_user_id, action, user_id, check_id,
ip, created_at`. Every admin route writes one row.

### Rules

* **Sign-up** (`POST /api/auth/register {phone, password, app}`): customer app
  only. Password 8 to 128 characters, not all digits. Creates the user
  unverified, opens a `verify_number` check and returns a session.
* **Sign-in** (`POST /api/auth/login {phone, password, app}`): same session
  roles as today (`session_role`). 5 wrong passwords lock the number for
  15 minutes; rate limits per IP as on the old OTP routes. The answer never
  says whether a number exists, except the existing "not a merchant / not an
  admin" messages after a correct password.
* **Unverified sessions:** the access token carries `verified: false`. Such a
  session can read `/api/auth/me`, enter the code, correct its number and sign
  out; every other route answers 403 `number_not_verified`. In particular no
  points, payments or consent are tied to an unverified number, so signing up
  with someone else's number shows nothing.
* **Enter the code** (`POST /api/auth/verify-number {code}`): 5 attempts per
  code, then the check goes back to `pending` for a new code. On success
  `phone_verified_at` is set and a new token pair is issued with
  `verified: true`. The loyalty consent given at sign-up is recorded at this
  moment, not before.
* **Correct the number before verification** (`POST /api/auth/number`): moves
  the account to the new number if free, reopens the check.
* **Existing accounts** (no password): sign-in answers `password_not_set`; the
  app shows « Créer votre mot de passe », which calls `register` and lands in
  the same unverified state. Their data reappears after verification. Nobody
  can take over an existing number without the WhatsApp code.
* **Forgotten password** (`POST /api/auth/password-reset {phone}`): opens a
  `reset_password` check; the answer is the same whether the number exists or
  not. The admin sends a temporary password (10 characters); using it signs the
  person in with `must_change_password` and counts as a verified number.
* **Change password** (`POST /api/auth/password {current, new}`): signs out
  every other session (deletes the refresh token families).
* **Change of number** (replaces the two SMS codes in `app/api/account.py`):
  `POST /api/account/number {password, new_phone}` opens a `change_number`
  check; the team sends the code to the new number; entering it moves the
  account.
* **Lost number** (`/api/auth/recovery…`): the admin check in fidelia-installer
  stays; the code to the new number becomes a `verify_number` check on a new
  account, then the admin approves the transfer as today.
* **Merchant sign-up request** (`app/api/onboarding.py`): the code is removed;
  the team already calls the merchant before approving.
* **Merchant, cashier, agent and admin logins** created by the team or an
  owner get a generated temporary password and an open `reset_password` check
  in state `pending`, so it appears in Fidelia Admin to be sent on WhatsApp.

### Removed

`app/core/otp.py` (code parts; refresh-token helpers move to
`app/core/tokens.py`), `app/services/otp_sender.py`, `app/api/orange_sms.py`,
`/api/auth/otp/request`, `/api/auth/otp/verify`, `TEST_OTP_NUMBERS`,
`OTP_SENDER`, `OTP_DEV_ECHO`, the Orange settings in both `render*.yaml`, and
the demo `/token` route. The old OTP paths answer 410 with « Mettez à jour
l'application » so v0.2.1 phones see why they cannot sign in.

Test API: the seed gives the shared test numbers fixed passwords
(`07 00 00 00 01` customer, `07 00 00 00 02` merchant, `07 00 00 00 09` admin),
verified, refused when `FIDELIA_ENV=production`.

## 3. Admin API

All under `/api/admin/accounts`, `require_role("admin")`, each writing an
`admin_actions` row:

| Route | Does |
|---|---|
| `GET /checks?kind=` | open checks: app, masked number, kind, age, already sent |
| `POST /checks/{id}/send` | makes a new code or temporary password, stores its hash, marks `sent`, returns `{url}` |
| `POST /checks/{id}/refuse` | `refused`; the user sees « numéro non vérifié » and can correct it |
| `GET /users?phone=` | roles, disabled, verified, last sign-in |
| `POST /users/{id}/suspend` · `/restore` · `/sign-out` · `/reset-password` | as named; reset opens and returns a check |

The full number appears only inside the `wa.me` link; lists show it masked.

## 4. Fidelia Admin (new repository `fidelia-App-admin`)

Flutter, Riverpod and Dio like Flariane's `admin_app` (`core/`, `data/`,
`features/`, `widgets/`), Fidelia's colours and logo. Package
`com.regisse.fidelia.admin`, Android first, distributed privately (Play internal
testing or the release APK), never listed. Release workflow copied from
fidelia-App-retailer, its own signing key.

Sign-in with phone + password and `app: "admin"`; tokens in
`flutter_secure_storage`.

| Screen | Content |
|---|---|
| À traiter | counters « Numéros à vérifier » and « Mots de passe oubliés », pull to refresh |
| Numéros à vérifier | cards (app, masked number, age, « Code déjà envoyé »); **Envoyer le code sur WhatsApp**, **Refuser** with confirmation |
| Mots de passe oubliés | same, with **Envoyer un mot de passe temporaire sur WhatsApp** |
| Identifiants commerçant | new merchant/cashier logins whose temporary password is not sent yet |
| Utilisateurs | search a number; suspend/restore, sign out everywhere, reset password |
| Compte | change own password, sign out |

If WhatsApp cannot open, the app says so and leaves the check as `sent`, so a
retry makes a new code (the old one stops working).

## 5. Changes in the existing apps

* **Fidelia and Fidelia Pro (v0.3.0):** sign-in and sign-up screens with
  password; « Créer votre mot de passe » for existing numbers; the waiting
  screen « Fidelia va vous envoyer un code sur WhatsApp » with code entry and
  « Corriger mon numéro »; « Mot de passe oublié »; the forced password change;
  in Pro, adding a cashier no longer asks for a code. The update message for
  410 answers.
* **fidelia-installer:** password sign-in; creating a merchant login shows
  that its temporary password is waiting in Fidelia Admin.
* **Docs:** PLAY-STORE.md (Data safety: no SMS provider; reviewer accounts use
  a password), the privacy page (« l'équipe vous envoie un code sur WhatsApp »
  instead of the SMS provider), TECHNICAL-GUIDE sign-in section, changelogs.

## 6. Order of work

1. fidelia-BE: migration, password and admin routes, OTP removal, seed, tests.
2. fidelia-App-admin.
3. Fidelia and Fidelia Pro v0.3.0.
4. fidelia-installer.
5. Docs and privacy page.
6. Release: deploy the backend to the test API, tag v0.3.0 of both apps and
   v0.1.0 of Fidelia Admin; the v0.3.0 bundles go to Google Play.

Each step lands on `integration` and is checked before the next.

## 7. Testing

* **Backend (pytest):** register, login, lockout, `password_not_set`,
  unverified sessions blocked from loyalty and payment routes, code expiry,
  reuse and attempt limit, temporary password forcing a change, number
  correction and change, admin-only routes, `admin_actions` rows, 410 on old
  OTP paths, no import of an SMS sender left.
* **Flutter:** widget tests for the new sign-in, waiting and admin screens.
* **End to end** on the test API with an emulator: sign up in Fidelia, send
  the code from Fidelia Admin, enter it, see the counter points.

## Out of scope

Push notifications to admins, automatic WhatsApp Cloud API sending, iOS
builds, moving the installer's other screens into Fidelia Admin.
