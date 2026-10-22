# Fidelia Admin app Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A private Android app, Fidelia Admin, in which a team member signs in with phone + password and sends the WhatsApp codes and temporary passwords that replace SMS, and manages accounts.

**Architecture:** A new Flutter repository `fidelia/fidelia-App-admin` that copies the transport, token and theme layer of Fidelia Pro (`fidelia-App-retailer/lib/core/net`, `core/auth/token_store.dart`, `core/config/env.dart`, `ui/theme.dart`) and adds an admin `AuthRepository` (password routes) and an `AccountsApi` over `/api/admin/accounts`. Screens are thin Riverpod consumers. The backend is fidelia-BE `feature/password-signin`.

**Tech Stack:** Flutter (Dart ^3.5), flutter_riverpod, http, flutter_secure_storage, url_launcher. Tests: flutter_test with `http/testing.dart` MockClient.

**Spec:** `fidelia-docs/docs/superpowers/specs/2026-10-22-password-whatsapp-sign-in-design.md` § 4. API reference: the "Sign-in" section drafted from the backend (routes and status codes as implemented).

This is plan 2 of 5. Ruling: the spec says "Riverpod and Dio like Flariane"; this plan reuses Fidelia Pro's tested `http` core instead, so the three Fidelia apps share one network and auth layer.

## Global Constraints

- Repository: `/Users/regis/Development/com_regisse/fidelia/fidelia-App-admin` (new local git repo, branch `main`; remote added by the owner).
- Package `com.regisse.fidelia.admin`, app label `Fidelia Admin`, Dart package `fidelia_admin`, version `0.1.0+1`, `minSdk` and `targetSdk` same as Fidelia Pro (target API 36).
- API base from `--dart-define=FIDELIA_API_BASE=...` (Fidelia Pro's `Env`), HTTPS enforced in release.
- `FLAG_SECURE` on the activity (no screenshots of numbers and codes), like Flariane Admin.
- Sign-in body: `{"phone", "country_code": "CI", "password", "app": "admin"}` to `POST /api/auth/login`. Only the `admin` role gets a session.
- Admin routes: `GET /api/admin/accounts/checks?kind=verify_number|reset_password|change_number` → `[{id, kind, app, phone_masked, created_at, sent_at, team_created}]`; `POST /checks/{id}/send` → `{url}`; `POST /checks/{id}/refuse` → 204; `GET /users?phone=&country_code=CI` → `{id, phone_masked, roles, disabled, verified, last_login_at}` or 404; `POST /users/{id}/suspend|restore|sign-out` → 204; `POST /users/{id}/reset-password` → `{check_id}`. 409 `"Cette demande est deja traitee."` on a closed check.
- All UI text in French with accents (it is UI, not API). Screen and button wording exactly as in the spec § 4: « À traiter », « Numéros à vérifier », « Mots de passe oubliés », « Identifiants commerçant », « Utilisateurs », « Compte », « Envoyer le code sur WhatsApp », « Envoyer un mot de passe temporaire sur WhatsApp », « Refuser ».
- The full phone number never appears in the app's UI or logs; only `phone_masked`. The `wa.me` URL is opened with `url_launcher` in `LaunchMode.externalApplication` and never logged.
- `flutter analyze` clean and `flutter test` green before every commit. Commit footer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **WhatsApp is not installed or the link fails to open** → the app says « WhatsApp n'a pas pu s'ouvrir » and refreshes the list (the check stays `sent`; sending again makes a new code). Test in Task 5.
2. **Two admins handle the same request** → the second gets 409 and sees « Cette demande est déjà traitée », and the list refreshes. Test in Task 5.
3. **Admin signs in with a temporary password** (`must_change_password: true`) → only the change-password screen is reachable until the change succeeds. Test in Task 3.
4. **Access token expires while the app is open** → one refresh, retried request; a refused refresh returns to sign-in, not an error screen. Test in Task 2.
5. **Number not found in Utilisateurs** → « Aucun compte pour ce numéro », no crash on 404. Test in Task 6.

---

### Task 1: Scaffold the app on Fidelia Pro's core

**Files:**
- Create: the Flutter project (`flutter create --org com.regisse.fidelia --project-name fidelia_admin --platforms android fidelia-App-admin`), then rename the Android application id to `com.regisse.fidelia.admin` and the label to `Fidelia Admin`.
- Copy from `fidelia-App-retailer`: `lib/core/net/api_client.dart`, `lib/core/net/api_exception.dart`, `lib/core/config/env.dart`, `lib/core/auth/token_store.dart`, `lib/ui/theme.dart`, `analysis_options.yaml`, `test/env_test.dart`; remove anything those files import that is merchant-specific (usage tracker, traffic callbacks may stay as optional parameters).
- Modify: `android/app/src/main/kotlin/.../MainActivity.kt` (FLAG_SECURE), `pubspec.yaml` (dependencies above, version `0.1.0+1`), `lib/main.dart` (MaterialApp with the theme and a placeholder home `Text('Fidelia Admin')`).
- Create: `README.md` (what the app is, how to run it against the test API), `.gitignore` (Flutter default plus `android/key.properties`, `*.jks`).

**Interfaces:**
- Produces: `ApiClient`, `ApiException`, `Env`, `TokenStore`, `fideliaTheme` (whatever Pro's theme exports) with the same signatures as in Fidelia Pro.

- [ ] **Step 1:** Create the project and copy the files; `git init`, first commit of the untouched `flutter create` output.
- [ ] **Step 2:** Run `flutter analyze` and `flutter test` → `env_test` passes.
- [ ] **Step 3:** Build `flutter build apk --debug --dart-define=FIDELIA_API_BASE=https://<test api>` succeeds.
- [ ] **Step 4: Commit** `Scaffold Fidelia Admin on Fidelia Pro's core`.

### Task 2: Admin sign-in repository

**Files:**
- Create: `lib/core/auth/auth_repository.dart`, `test/auth_repository_test.dart`
- Create: `lib/core/providers.dart` (ApiClient wired with token provider, refresh and unauthorized callbacks, like Pro's providers but only what this app needs)

**Interfaces:**
- Produces:
  - `sealed class SignInResult`: `SignedIn({required bool mustChangePassword})`, `SignInRejected(String message)`, `SignInUnavailable(String message)`
  - `AuthRepository.signIn({required String phone, required String password}) -> Future<SignInResult>`: 401/423/403/409 map to `SignInRejected` with the server's `detail` (409 `password_not_set` → « Ce compte n'a pas encore de mot de passe. Demandez-en un à l'équipe Fidelia. »); network/5xx → `SignInUnavailable`.
  - `refresh() -> Future<bool>` (single-flight, as Pro), `signOut()`, `hasValidSession()`, `mustChangePassword() -> Future<bool>` (from the stored token's `pc` claim), `changePassword({String? current, required String newPassword}) -> Future<void>` (throws `AccountActionException(message)` with the server's detail on 401/422).

- [ ] **Step 1: Tests (MockClient):** `signs in an admin`, `wrong password shows the server message`, `password_not_set has its own message`, `locked account (423) shows the server message`, `no network is unavailable, not rejected`, `temporary password session must change it`, `change password stores the new pair and clears the flag`, `expired token refreshes once then retries` (Review Focus 4), `refused refresh signs out`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS, analyze clean.
- [ ] **Step 5: Commit** `Admin sign-in with phone and password`.

### Task 3: Sign-in, forced change and the session gate

**Files:**
- Create: `lib/features/sign_in_screen.dart`, `lib/features/change_password_screen.dart`, `lib/features/session_gate.dart`, `test/sign_in_screen_test.dart`, `test/session_gate_test.dart`
- Modify: `lib/main.dart` (home = `SessionGate`)

**Interfaces:**
- Consumes: Task 2 `AuthRepository`, providers.
- Produces: `SessionGate` shows `SignInScreen` (no session), `ChangePasswordScreen(forced: true)` (session with `pc`), else `HomeScreen` (Task 5; a placeholder until then). `ChangePasswordScreen(forced: false)` is reused from Compte (Task 6) with a « Mot de passe actuel » field.

- [ ] **Step 1: Widget tests:** `sign-in sends phone and password`, `server message is shown under the form`, `forced change screen has no back button and no current-password field` (Review Focus 3), `after the change the gate shows home`, `password rules shown inline (8 caractères minimum, pas seulement des chiffres)`.
- [ ] **Step 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Commit** `Sign-in and forced password change screens`.

### Task 4: Accounts API client

**Files:**
- Create: `lib/core/accounts/accounts_api.dart`, `lib/core/accounts/models.dart`, `test/accounts_api_test.dart`

**Interfaces:**
- Produces:
  - `class AccountCheck {int id; String kind; String app; String phoneMasked; DateTime createdAt; DateTime? sentAt; bool teamCreated}` with `fromJson`
  - `class AdminUserView {int id; String phoneMasked; List<String> roles; bool disabled; bool verified; DateTime? lastLoginAt}`
  - `AccountsApi.checks(String kind) -> Future<List<AccountCheck>>`, `send(int id) -> Future<Uri>`, `refuse(int id)`, `findUser(String phone) -> Future<AdminUserView?>` (null on 404), `suspend(int)`, `restore(int)`, `signOut(int)`, `resetPassword(int) -> Future<int>`
  - `class AlreadyHandled implements Exception` thrown on 409 from send/refuse.

- [ ] **Step 1: Tests:** each method's path, method and parsing; 409 → `AlreadyHandled`; 404 on findUser → null; 403 → `ApiException` (not admin).
- [ ] **Step 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Commit** `Client for the admin accounts routes`.

### Task 5: À traiter and the three request lists

**Files:**
- Create: `lib/features/home_screen.dart` (À traiter: three counters with their lists), `lib/features/checks_screen.dart`, `lib/features/whatsapp.dart` (open a URI, return bool), `test/checks_screen_test.dart`
- Modify: `lib/features/session_gate.dart` (real home)

**Interfaces:**
- Consumes: `AccountsApi`, `AccountCheck`, `AlreadyHandled`.
- Lists: « Numéros à vérifier » = `verify_number` + `change_number`; « Mots de passe oubliés » = `reset_password` with `teamCreated == false`; « Identifiants commerçant » = `reset_password` with `teamCreated == true`. Card: app chip (Fidelia / Fidelia Pro), masked number, « il y a 3 h », « Code déjà envoyé » when `sentAt != null`. Buttons per spec § 4; « Refuser » asks for confirmation. Pull to refresh; refresh after every action.

- [ ] **Step 1: Widget tests (fake `AccountsApi`, fake launcher):** `lists are split by kind and origin`, `send opens the WhatsApp link and refreshes`, `WhatsApp failing shows the message and refreshes` (Review Focus 1), `already handled shows the message and refreshes` (Review Focus 2), `refuse needs confirmation`, `empty list says « Rien à traiter »`.
- [ ] **Step 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Commit** `Request lists with WhatsApp sending`.

### Task 6: Utilisateurs and Compte

**Files:**
- Create: `lib/features/users_screen.dart`, `lib/features/account_screen.dart`, `test/users_screen_test.dart`
- Modify: `lib/features/home_screen.dart` (navigation: bottom bar À traiter / Utilisateurs / Compte)

**Interfaces:**
- Users: number field (Ivorian national format), search → card with masked number, roles, « Vérifié » / « Non vérifié », « Suspendu », last sign-in; actions « Suspendre » / « Réactiver », « Déconnecter partout », « Réinitialiser le mot de passe » (each with confirmation; reset then opens the new check's send flow by refreshing « Mots de passe oubliés »).
- Compte: « Changer mon mot de passe » (`ChangePasswordScreen(forced: false)`), « Se déconnecter ».

- [ ] **Step 1: Widget tests:** `unknown number shows « Aucun compte pour ce numéro »` (Review Focus 5), `suspend asks and calls the API`, `restore shown only for a suspended account`, `sign out returns to the sign-in screen`.
- [ ] **Step 2–4:** RED, implement, GREEN.
- [ ] **Step 5: Commit** `Users and account screens`.

### Task 7: Release build and docs

**Files:**
- Copy and adapt from `fidelia-App-retailer`: `.github/workflows/release.yml` (APK + Play bundle, signing secrets, `FIDELIA_API_BASE` variable; release name « Fidelia Admin »; no Firebase steps), `scripts/create-signing-key.sh`, `scripts/check-signing-key.sh`, `scripts/build-release.sh`, `android/app/build.gradle*` signing config from `key.properties`.
- Create: `CHANGELOG.md` (`## v0.1.0 — <date>`), launcher icon from `fidelia-brand/fidelia-app-icon.svg` with an « Admin » distinction (reuse Pro's `scripts/make-icons.py` approach).
- Modify: `README.md` (release: tag `v0.1.0`; distribution: Play internal testing or the APK, never public).

- [ ] **Step 1:** `flutter build apk --release --dart-define=FIDELIA_API_BASE=https://example.invalid` with a throwaway local key → builds, and `apksigner verify` passes.
- [ ] **Step 2:** `flutter analyze` clean, `flutter test` green.
- [ ] **Step 3: Commit** `Release workflow, signing and icon`.
