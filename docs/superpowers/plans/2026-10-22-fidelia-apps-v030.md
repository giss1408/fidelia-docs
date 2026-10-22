# Fidelia and Fidelia Pro v0.3.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SMS-code sign-in in Fidelia (customers) and Fidelia Pro (merchants) with phone + password and the WhatsApp checks the team sends from Fidelia Admin, and make both apps' release workflows safe, so v0.3.0 can go to Google Play.

**Architecture:** In each app, `lib/core/auth/auth_repository.dart` drops the code methods and gains the password routes; the sign-in UI becomes a password form with « Mot de passe oublié »; a session that is not verified (`verified: false`) or must change its password (`must_change_password: true`) is held on a dedicated screen until resolved. `lib/core` stays UI-free (ARCHITECTURE.md rule).

**Tech Stack:** Flutter 3.24, Riverpod, http, flutter_secure_storage (existing). Tests: flutter_test with MockClient and the apps' existing fakes.

**Spec:** `fidelia-docs/docs/superpowers/specs/2026-10-22-password-whatsapp-sign-in-design.md` § 5. API as implemented: the "Sign-in" section drafted from fidelia-BE `feature/password-signin` (routes, bodies, status codes). Plan 3 of 5.

## Global Constraints

- Repositories: `fidelia/fidelia-App-user` (Fidelia, package `com.regisse.fidelia`) and `fidelia/fidelia-App-retailer` (Fidelia Pro, `com.regisse.fidelia.pro`). Each on a new branch `feature/password-signin` from `integration`.
- Version `0.3.0` in both (`CHANGELOG.md` section `## v0.3.0 — <date>`, `android/fastlane/metadata/android/fr-FR/changelogs/default.txt` ≤ 500 characters).
- API (all under `/api`, `country_code: "CI"`):
  - `POST /auth/login {phone, country_code, password, app}` → pair `{access_token, refresh_token, token_type, expires_in, role, phone_masked, verified, must_change_password}`; 401 wrong number or password (same message), 423 locked, 409 `{"detail":"password_not_set"}`, 403 suspended / role missing.
  - `POST /auth/register {phone, country_code, password, app:"customer", loyalty_consent_version?}` → 201 pair (new number, `verified:false`) or 202 `{message}` (existing account without a password: no session) ; 409 number already has a password ; 422 weak password.
  - `POST /auth/claim {phone, country_code, code, password, app, loyalty_consent_version?}` → pair (verified) ; 401 « Code incorrect ou expire. » ; 422 ; 403.
  - `POST /auth/verify-number {code}` (unverified session) → pair (verified) ; 401.
  - `POST /auth/number {phone, country_code}` (unverified session) → pair ; 409 taken ; 422 same ; 403.
  - `POST /auth/password-reset {phone, country_code}` → 202 `{message}` always.
  - `POST /auth/password {current?, new}` → pair ; `current` ignored only for a `pc` session ; 401 wrong current ; 422.
  - `POST /auth/change-number/request {password, new_phone, country_code}` → 202 `{new_phone_masked}` ; `POST /auth/change-number/confirm {code}` → pair.
  - `POST /auth/recovery {old_phone, country_code, details}` (verified session on the NEW number) → 202 `{message}`.
  - `GET /auth/me` → `{sub, role, phone_masked, verified, must_change_password, number_refused}`.
  - Any route answers 403 `number_not_verified` or `password_change_required` for a held session.
  - Removed: `/auth/otp/*` (410), `/auth/recovery/code`, `/auth/change-number` two-code bodies, `/partner-requests/code` and the `code` field of `/partner-requests`.
- Password rule shown and checked client-side: « 8 caractères minimum, pas seulement des chiffres » (server stays the authority; show its message).
- UI text French with accents. Never log or show a full phone number, a code or a password.
- Release workflows: no `${{ }}` inside any `run:` block; the tag is validated against `^v[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$` (same fix as fidelia-App-admin `0e705b1`).
- `flutter analyze` clean and `flutter test` green before every commit. Commit footer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **An existing customer (account from v0.2, no password)** taps « Se connecter » → 409 → the app offers « Créer votre mot de passe », then the 202 path leads to « Saisissez le code reçu sur WhatsApp et votre mot de passe » (claim), never to a dead end. Test in Task 2.
2. **A new customer** gets a session but `verified: false` → held on « En attente de votre code WhatsApp » with code entry, « Corriger mon numéro », and the refused-number message; `ensureSignedIn` stays false until verified, so paying is never reached unverified. Test in Task 3.
3. **A merchant whose login the team created** (no password) → « Mot de passe oublié » path: the team sends a temporary password; signing in with it forces « Choisissez votre mot de passe ». Test in Task 7.
4. **A held session hits a data route** (403 `number_not_verified` / `password_change_required`) → the app routes to the holding screen instead of showing a raw error. Test in Tasks 3 and 7.
5. **A crafted tag** on the release workflows cannot run shell code. Checked in Tasks 5 and 9.

---

## Fidelia (customer app, `fidelia-App-user`)

### Task 1: Customer auth repository on passwords

**Files:** Modify `lib/core/auth/auth_repository.dart`, `lib/core/auth/token_store.dart` (read `vf`/`pc` claims), `test/auth_test.dart`.

**Interfaces (produced):**
- `sealed class LoginResult`: `SignedIn({required bool verified, required bool mustChangePassword})`, `PasswordNotSet()`, `LoginRejected(String message)`, `LoginUnavailable(String message)`.
- `sealed class RegisterResult`: `SessionOpened({required bool verified})` (201), `ClaimNeeded(String message)` (202), `RegisterRejected(String message)`, `RegisterUnavailable(String message)`.
- `login(phone, password)`, `register(phone, password, {String? loyaltyConsentVersion})`, `claim(phone, code, password, {String? loyaltyConsentVersion}) -> LoginResult`, `verifyNumber(code) -> Future<void>` (throws `AccountActionException`), `correctNumber(phone)`, `requestPasswordReset(phone) -> Future<String>` (the message), `changePassword({String? current, required String newPassword})`, `requestNumberChange({password, newPhone}) -> Future<String>` (masked new number), `confirmNumberChange(code)`, `fileRecovery({oldPhone, details}) -> Future<String>`, `me() -> Future<MeInfo>` (`verified`, `mustChangePassword`, `numberRefused`, `phoneMasked`).
- `isVerified()` / `mustChangePassword()` from the stored token claims (missing `vf` = verified).
- Removed: `requestCode`, `verifyCode`, `requestRecoveryCode`, the two-code number change, `CodeSent`/`NumberChangeCodes` types.
- `ApiClient`: a 401 on `/auth/password` and on code entry must not end the session (port fidelia-App-admin's `unauthorizedEndsSession` flag).

- [ ] **Step 1: Tests (MockClient):** login ok / 401 / 423 / 409 → `PasswordNotSet` / offline; register 201 unverified / 202 claim / 409 / 422; claim ok stores a verified pair; verifyNumber stores the new pair; wrong code keeps the session; password reset returns the server message; change password with and without current; number change request + confirm; recovery; `me()` parsing.
- [ ] **Step 2–4:** RED, implement, GREEN; `flutter analyze` clean.
- [ ] **Step 5: Commit** `Customer sign-in with a password`.

### Task 2: Sign-in, sign-up and claim screens

**Files:** Replace `lib/features/phone_sign_in_form.dart` with `lib/features/password_sign_in_form.dart`; create `lib/features/claim_screen.dart`, `lib/features/forgot_password_screen.dart`; modify `lib/features/sign_in_screen.dart`, `lib/l10n/strings.dart`; tests `test/sign_in_test.dart`.

**Behaviour:** One form with two modes, « Se connecter » and « Créer un compte » (switch link). Create mode shows the existing loyalty consent tick (same wording/version as today) and the password rule. Login 409 → switches to create mode with « Ce numéro a déjà un compte Fidelia. Créez votre mot de passe. ». Register 202 → `ClaimScreen` (code + password + confirmation; text « Fidelia va vous envoyer un code sur WhatsApp. ») ; register 201 → back to the caller with an unverified session (Task 3 holds it). « Mot de passe oublié ? » → `ForgotPasswordScreen` (number → server message → « Retour à la connexion »).

- [ ] **Step 1: Widget tests:** sign-in sends phone + password; 409 switches to create mode with the message (Review Focus 1); 202 opens the claim screen and a successful claim closes sign-in signed in; weak password blocked client-side; forgot password shows the server message.
- [ ] **Step 2–4:** RED, implement, GREEN. **Step 5: Commit** `Password sign-in, sign-up and claim screens`.

### Task 3: Holding screens and gates

**Files:** Create `lib/features/waiting_for_code_screen.dart`, `lib/features/change_password_screen.dart` (forced and non-forced, as in fidelia-App-admin); modify `lib/core/providers.dart` (session state: `signedIn` only when verified and not `pc`; new `held` states), `lib/features/sign_in_gate.dart`, `lib/features/shell.dart` (or wherever 403 surfaces); tests `test/holding_test.dart`.

**Behaviour:** `ensureSignedIn` returns true only for a verified, non-`pc` session; an unverified session opens `WaitingForCodeScreen`: « Fidelia va vous envoyer un code sur WhatsApp au 07 •• •• 56 78 », code field, « Valider », « Corriger mon numéro » (dialog → `/auth/number`), the refused message « Ce numéro n'a pas pu être vérifié. Corrigez-le ou contactez Fidelia. » when `me().numberRefused`, « Se déconnecter ». A `pc` session opens the forced `ChangePasswordScreen`. Any 403 `number_not_verified` / `password_change_required` from a data call routes to the matching screen (Review Focus 4).

- [ ] **Step 1: Widget tests:** unverified session → waiting screen and `ensureSignedIn` false (Review Focus 2); correct code → signed in; wrong code shows the server message and keeps the session; refused number shows the message; correct number flow; `pc` session → forced change; a 403 from a data call routes to the right screen.
- [ ] **Step 2–4:** RED, implement, GREEN. **Step 5: Commit** `Hold unverified and must-change sessions`.

### Task 4: Account screen

**Files:** Modify `lib/features/account_screen.dart`, `lib/l10n/strings.dart`; tests `test/account_test.dart`.

**Behaviour:** Add « Changer mon mot de passe » (non-forced change screen). Number change: password + new number → « Fidelia va envoyer un code sur WhatsApp au … » → code → done (« Votre compte est maintenant sur ce numéro »). Lost number: « J'ai perdu mon ancien numéro » now explains the person is signed in on the new number and files `/auth/recovery {old_phone, details}`; no code step. Keep « Déconnecter mes autres appareils » and account deletion unchanged.

- [ ] **Step 1: Widget tests:** password change; number change request + confirm; recovery filing; wrong password on number change shows the message.
- [ ] **Step 2–4:** RED, implement, GREEN. **Step 5: Commit** `Account: password and number changes without SMS`.

### Task 5: Release workflow, version, changelog

**Files:** `.github/workflows/release.yml` (tag validation, values through `env:`, as fidelia-App-admin `0e705b1`), `pubspec.yaml` (`0.3.0+1`), `CHANGELOG.md`, `android/fastlane/metadata/android/fr-FR/changelogs/default.txt` (« Connexion par mot de passe. Votre numéro est confirmé une fois par un code WhatsApp de l'équipe Fidelia. » + the v0.2.1 lines kept within 500 characters), README sign-in section.

- [ ] **Step 1:** Parse release.yml (`python3 -I -c "import yaml"` or `ruby -ryaml`) and assert no `${{` inside `run:` blocks (Review Focus 5); `bash -n` on scripts.
- [ ] **Step 2:** `flutter build apk --debug` succeeds; analyze clean; tests green.
- [ ] **Step 3: Commit** `Release v0.3.0 preparation`.

## Fidelia Pro (merchant app, `fidelia-App-retailer`)

### Task 6: Merchant auth repository on passwords

**Files:** `lib/core/auth/auth_repository.dart`, `lib/core/auth/token_store.dart`, `lib/core/net/api_client.dart` (port `unauthorizedEndsSession`), `test/auth_test.dart`.

**Interfaces:** As Task 1 minus `register` and `claim`: `login` (app `"merchant"`; the session role is `merchant` or `cashier` as today), `requestPasswordReset`, `changePassword`, `requestNumberChange` / `confirmNumberChange`, `fileRecovery`, `me()`, `isVerified()`, `mustChangePassword()`. `PasswordNotSet` on 409. Removed: code methods, `requestPartnerCode`; `filePartnerRequest` no longer takes a code.

- [ ] **Step 1–4:** Tests mirroring Task 1 for these methods, plus partner request without code; RED, implement, GREEN.
- [ ] **Step 5: Commit** `Merchant sign-in with a password`.

### Task 7: Merchant sign-in, forgot password and forced change

**Files:** Replace `lib/features/phone_sign_in_form.dart` with a password form; create `lib/features/forgot_password_screen.dart`, `lib/features/change_password_screen.dart`; modify `lib/features/sign_in_screen.dart`, the session gate in `lib/main.dart` / home, `lib/l10n/strings.dart`; tests `test/sign_in_test.dart`.

**Behaviour:** « Se connecter » with phone + password; 409 `password_not_set` → « Votre compte n'a pas encore de mot de passe. Fidelia va vous en envoyer un sur WhatsApp. » and calls `requestPasswordReset` automatically (shows the server message). « Mot de passe oublié ? » → same screen as the customer app. A `pc` session → forced « Choisissez votre mot de passe » (Review Focus 3). 403 `password_change_required` from any call → forced screen (Review Focus 4). Pro has no unverified-number path (team-created logins are verified by their temporary password), but a `verified:false` session shows « Votre numéro n'est pas encore vérifié. Contactez Fidelia. » with « Se déconnecter ».

- [ ] **Step 1–4:** Widget tests for each behaviour; RED, implement, GREEN.
- [ ] **Step 5: Commit** `Merchant password sign-in and forced change`.

### Task 8: Merchant account, staff and partner request

**Files:** `lib/features/account_screen.dart`, `lib/features/staff_screen.dart`, `lib/features/partner_request_screen.dart`, `lib/l10n/strings.dart`, tests.

**Behaviour:** Account: change password; number change as Task 4; recovery as Task 4. Staff: after adding a cashier, say « Fidelia va envoyer un mot de passe temporaire sur WhatsApp à votre caissier. » (no SMS wording anywhere). Partner request: no code step; the form posts directly and shows the server message.

- [ ] **Step 1–4:** Widget tests; RED, implement, GREEN; `grep -ri "sms" lib` shows no user-facing SMS wording.
- [ ] **Step 5: Commit** `Merchant account, staff and partner request without SMS`.

### Task 9: Release workflow, version, changelog

As Task 5 for Fidelia Pro (changelog text: « Connexion par mot de passe. L'équipe Fidelia vous envoie votre premier mot de passe sur WhatsApp. »).

- [ ] **Step 1–3:** Same checks; **Commit** `Release v0.3.0 preparation`.

## After both apps

Push both `feature/password-signin` branches and open PRs into `integration` (owner merges). Tagging `v0.3.0` waits until the backend is deployed to the test API and an end-to-end run works on a phone: sign up in Fidelia → send the code from Fidelia Admin → enter it → see points; merchant temporary password → forced change → home.
