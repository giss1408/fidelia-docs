# Password sign-in, backend (fidelia-BE) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every SMS code in the Fidelia API with phone + password sign-in, one-time WhatsApp number checks sent by the team, and the admin routes Fidelia Admin needs.

**Architecture:** Passwords are argon2id hashes on `users`. Every "the team must send something on WhatsApp" is one row in a new `account_checks` table; `app/services/account_checks.py` opens, sends (returns a `wa.me` link), verifies and refuses them. The access token carries `vf` (number verified) and `pc` (password change required); `get_current_user` refuses either, and the few routes such a session may use depend on `get_session_user` instead.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, pytest + httpx, `argon2-cffi`.

**Spec:** `fidelia-docs/docs/superpowers/specs/2026-10-22-password-whatsapp-sign-in-design.md`

This is plan 1 of 5 (backend). Plans 2–5 (Fidelia Admin app, Fidelia and Fidelia Pro v0.3.0, fidelia-installer, docs and release) are written after this one lands, against the routes it produces.

## Global Constraints

- Work in `fidelia-BE` on a branch from `integration` (`git checkout integration && git pull && git checkout -b feature/password-signin`); paths below are relative to `fidelia-BE/backend-api/`.
- Run tests with `cd fidelia-BE/backend-api && pytest -q` (SQLite, `tests/conftest.py`).
- Password: 8 to 128 characters, not all digits. Hash: argon2id.
- Codes: 6 digits. Temporary passwords: 10 characters from `ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789`.
- Codes and temporary passwords expire **24 h after sending**; 5 wrong attempts void a code (check returns to `pending`). Only an HMAC (keyed on `FIDELIA_SECRET_KEY`) is stored.
- Wrong password: 5 in a row lock the number for 15 minutes.
- User-facing messages in French without accents, like the existing API messages (`"Code incorrect ou expire."`).
- WhatsApp message text, exactly (accents allowed, it is WhatsApp):
  - code: `Bonjour, voici votre code Fidelia : {code}. Saisissez-le dans l'application. Valable 24 h. Ne le partagez avec personne.` (code shown as `482 913`)
  - temporary password: `Bonjour, votre mot de passe temporaire Fidelia : {password}. Vous devrez en choisir un nouveau a la connexion.`
- No SMS: after Task 8, `grep -rn "otp_sender\|orange_sms\|OTP_SENDER\|TEST_OTP_NUMBERS" app ../render*.yaml` prints nothing.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Someone registers an existing customer's number** → they get an unverified session that sees no points, no payments, no consent; the real owner's password (if any) is untouched. Test in Task 3 and Task 4.
2. **Existing users on v0.2.1 mid-session** → their refresh tokens keep working (migration marks them verified), and the old OTP paths answer 410 with the update message. Test in Task 1 and Task 8.
3. **Admin sends a code twice** (WhatsApp failed to open) → the second send makes a new code and the first stops working. Test in Task 2.
4. **A temporary password is used** → the session can only change the password; after the change every other session is gone. Test in Task 5.
5. **Number lookups leak** → `password-reset` and `login` with an unknown number answer exactly like a known one (same status, same body). Test in Task 3 and Task 5.

---

### Task 1: Schema, passwords and token helpers

**Files:**
- Create: `app/core/passwords.py`, `app/core/tokens.py`, `alembic/versions/0029_password_signin.py`, `tests/test_passwords.py`
- Modify: `app/models.py` (`User`, new `AccountCheck`, `AdminAction`), `requirements.txt` (add `argon2-cffi`)

**Interfaces:**
- Produces:
  - `passwords.hash_password(plain: str) -> str`, `passwords.verify_password(plain: str, hashed: str) -> bool`, `passwords.check_rules(plain: str) -> None` (raises `ValueError` with the French message)
  - `tokens.new_refresh_token()`, `tokens.hash_refresh_token(t)`, `tokens.new_family()` (moved from `core/otp.py`; `otp.py` re-exports them until Task 8), `tokens.hmac_secret(user_id: int, kind: str, secret: str) -> str`, `tokens.secret_matches(user_id, kind, secret, stored) -> bool`
  - `models.User` new columns: `password_hash`, `must_change_password` (bool, default false), `phone_verified_at`, `failed_logins` (int, default 0), `locked_until`
  - `models.AccountCheck` (table `account_checks`, columns as in the spec § 2 Data) and `models.AdminAction` (table `admin_actions`)

- [ ] **Step 1: Write the failing tests** in `tests/test_passwords.py`: `test_hash_roundtrip` (verify true for the right password, false for another), `test_rules_reject_short_and_all_digits` (`"1234567"`, `"12345678"` raise; `"motdepasse1"` passes), `test_secret_hmac_is_bound_to_user_and_kind` (same secret, other user or other kind → no match).
- [ ] **Step 2: Run** `pytest tests/test_passwords.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** `passwords.py` with `argon2.PasswordHasher()`, `tokens.py`, the model columns, and migration `0029_password_signin` (down_revision `0028_pilot_merchants`) that adds the columns and both tables, then runs `UPDATE users SET phone_verified_at = COALESCE(last_login_at, created_at)`: existing users proved their number by SMS, so their sessions keep working.
- [ ] **Step 4: Run** `pytest -q` → all pass (nothing else changed yet), and `alembic upgrade head` on a scratch SQLite database succeeds.
- [ ] **Step 5: Commit** `git commit -m "Add password hashes, account checks and admin actions"`

### Task 2: Account checks and WhatsApp links

**Files:**
- Create: `app/services/whatsapp.py`, `app/services/account_checks.py`, `tests/test_account_checks.py`

**Interfaces:**
- Consumes: Task 1 models and `tokens.hmac_secret`.
- Produces:
  - `whatsapp.whatsapp_link(e164: str, message: str) -> str` → `https://wa.me/<digits without +>?text=<urlencoded>`
  - `account_checks.open_check(db, user, kind, now, new_phone_e164=None) -> AccountCheck` (reuses an open one of the same kind)
  - `account_checks.send_check(db, check, admin_user_id, now) -> str` (new secret, `status="sent"`, `expires_at=now+24h`, attempts 0; returns the link; the message goes to `new_phone_e164` for `change_number`, else the user's number)
  - `account_checks.verify_code(db, user, kind, code, now) -> AccountCheck` (raises `BadCode`; on 5th wrong attempt sets `status="pending"`, clears the secret)
  - `account_checks.use_temporary_password(db, user, password, now) -> bool`
  - `account_checks.refuse(db, check, now)`; `BadCode` exception

- [ ] **Step 1: Write the failing tests:** `test_link_encodes_number_and_text` (`+2250701020304` → starts with `https://wa.me/2250701020304?text=Bonjour`), `test_code_message_spaces_the_code` (`482 913` in the decoded text), `test_open_check_reuses_the_open_one`, `test_resend_voids_the_previous_code` (Review Focus 3), `test_code_expires_after_24h`, `test_five_wrong_codes_send_the_check_back_to_pending`, `test_change_number_message_goes_to_the_new_number`, `test_temporary_password_works_once`.
- [ ] **Step 2: Run** `pytest tests/test_account_checks.py -q` → FAIL.
- [ ] **Step 3: Implement** both modules. Codes from `secrets.randbelow`, temporary passwords from `secrets.choice` over the alphabet in Global Constraints.
- [ ] **Step 4: Run** `pytest tests/test_account_checks.py -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Account checks: codes and temporary passwords sent on WhatsApp"`

### Task 3: Register and log in

**Files:**
- Create: `app/api/password_auth.py`, `tests/helpers.py`, `tests/test_password_auth.py`
- Modify: `app/api/auth.py` (`issue_tokens` adds the `vf` and `pc` claims; `refresh` re-reads them from the user), `app/main.py` (include the router under `/api`)

**Interfaces:**
- Consumes: Tasks 1–2; `session_role`, `_GRANTED_ONLY`, `phone_or_422`, `issue_tokens`, `TokenPairOut` from `app/api/auth.py`.
- Produces:
  - `POST /api/auth/register {phone, country_code="CI", password, app: "customer", loyalty_consent_version?}` → 201 `TokenPairOut` + `verified: false`; stores `loyalty_consent_version` on the open `verify_number` check (new nullable column `consent_version` on `account_checks`, add to migration 0029)
  - `POST /api/auth/login {phone, country_code, password, app}` → `TokenPairOut` + `verified` + `must_change_password`; errors: 401 `"Numero ou mot de passe incorrect."` (also for unknown numbers), 409 `{"detail": "password_not_set"}` for a known number without a password, 423 `"Trop d'essais. Reessayez dans 15 minutes."`, 403 as today for suspended / not merchant / not admin (only after a correct password)
  - `TokenPairOut` gains `verified: bool` and `must_change_password: bool`
  - `tests/helpers.py`: `async def make_user(phone, roles="customer", password="motdepasse1", verified=True) -> None` and `async def sign_in(ac, phone, app="customer", password="motdepasse1") -> httpx.Response`
- Rules: register on a number that already has a password → 409 `"Ce numero a deja un compte. Connectez-vous."`; register on a number without a password (existing account) sets the hash and **clears `phone_verified_at`** and opens a `verify_number` check. Rate limits: register `5/minute;20/hour`, login `10/minute;30/hour` (per IP, `limiter`).

- [ ] **Step 1: Write the failing tests:** `test_register_gives_an_unverified_session`, `test_register_twice_is_refused`, `test_existing_account_without_password_must_create_one` (login → 409 `password_not_set`; register → unverified, `phone_verified_at` cleared), `test_login_with_right_password`, `test_unknown_number_and_wrong_password_look_the_same` (Review Focus 5: same status and body), `test_five_wrong_passwords_lock_for_15_minutes`, `test_merchant_app_needs_the_merchant_role`, `test_suspended_account_is_refused`, `test_refresh_keeps_the_verified_claim`, `test_weak_password_is_refused` (422).
- [ ] **Step 2: Run** `pytest tests/test_password_auth.py -q` → FAIL.
- [ ] **Step 3: Implement** the router, the claims in `issue_tokens`, and `tests/helpers.py` (writes the user directly through `AsyncSessionLocal`).
- [ ] **Step 4: Run** `pytest -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Sign in and sign up with a phone number and a password"`

### Task 4: Unverified and must-change sessions

**Files:**
- Modify: `app/core/security.py`, `app/api/auth.py` (`/auth/me`, `/auth/logout` use `get_session_user`), `app/api/password_auth.py`
- Test: `tests/test_session_gates.py`

**Interfaces:**
- Produces:
  - `security.get_session_user` (accepts any valid token; returns the dict with `verified` and `must_change_password` added)
  - `security.get_current_user` (same, but 403 `{"detail": "number_not_verified"}` when `vf` is false and 403 `{"detail": "password_change_required"}` when `pc` is true). Tokens without `vf` count as verified (issued before this change, by SMS).
  - `/auth/me` returns `verified` and `must_change_password`
  - `POST /api/auth/verify-number {code}` (session user) → new `TokenPairOut` with `verified: true`; records the stored loyalty consent through `loyalty_consent.grant`; 401 `"Code incorrect ou expire."`
  - `POST /api/auth/number {phone, country_code}` (unverified sessions only) → moves the not-yet-verified account to the new number if free (409 otherwise), reopens the check, returns a new `TokenPairOut`

- [ ] **Step 1: Write the failing tests:** `test_unverified_session_sees_no_points` (Review Focus 1: register a number that has counter points via the seed, `GET` the customer's loyalty route → 403 `number_not_verified`), `test_unverified_session_can_read_me_and_log_out`, `test_code_from_the_team_verifies_the_number` (send the check with `account_checks.send_check`, read the code from the link, verify → points visible), `test_consent_given_at_sign_up_is_recorded_on_verification`, `test_unverified_user_can_correct_the_number`, `test_old_tokens_without_vf_still_work`.
- [ ] **Step 2: Run** `pytest tests/test_session_gates.py -q` → FAIL.
- [ ] **Step 3: Implement** the two dependencies and both routes.
- [ ] **Step 4: Run** `pytest -q` → PASS (the existing suite signs in through OTP tokens without `vf`, so it is unaffected).
- [ ] **Step 5: Commit** `git commit -m "Hold unverified and must-change sessions to the routes they need"`

### Task 5: Forgotten and changed passwords

**Files:**
- Modify: `app/api/password_auth.py`
- Test: `tests/test_password_reset.py`

**Interfaces:**
- Produces:
  - `POST /api/auth/password-reset {phone, country_code}` → always 202 `{"message": "Si ce numero a un compte, Fidelia vous enverra un mot de passe temporaire sur WhatsApp."}`; opens a `reset_password` check only for a known, active number. Rate limit `5/minute;20/hour`.
  - Login with a sent, unexpired temporary password → `TokenPairOut` with `must_change_password: true`; sets `phone_verified_at` if null.
  - `POST /api/auth/password {current, new}` (session user) → new `TokenPairOut`; clears `must_change_password`, revokes every other refresh family of the user (`account_move.revoke_all_sessions` with `keep_token_hash` of the new pair).

- [ ] **Step 1: Write the failing tests:** `test_reset_answer_is_the_same_for_unknown_numbers` (Review Focus 5), `test_temporary_password_forces_a_change` (Review Focus 4: with `pc`, `GET` a customer route → 403 `password_change_required`), `test_password_change_signs_out_other_sessions` (Review Focus 4: an older refresh token → 401), `test_temporary_password_expires_after_24h`, `test_old_password_still_works_until_the_temporary_one_is_used`.
- [ ] **Step 2: Run** `pytest tests/test_password_reset.py -q` → FAIL.
- [ ] **Step 3: Implement.** Login tries the password hash first, then `use_temporary_password`.
- [ ] **Step 4: Run** `pytest -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Forgotten password through the team, and password changes"`

### Task 6: Number change, recovery, partner requests and team-created logins

**Files:**
- Modify: `app/api/account.py`, `app/api/onboarding.py`, `app/api/auth.py` (`ensure_role`, `link_merchant`), `app/api/staff.py`
- Test: rewrite `tests/test_account_recovery.py`, `tests/test_onboarding.py`, `tests/test_enrollment_roles.py`; add `tests/test_team_created_logins.py`

**Interfaces:**
- Consumes: `account_checks.open_check(..., kind="change_number", new_phone_e164=...)`, `verify_code`.
- Produces:
  - `POST /api/auth/change-number/request {password, new_phone, country_code}` → 202, opens a `change_number` check (wrong password → 401). `POST /api/auth/change-number/confirm {code}` → moves the account with `move_account(..., method="self_service")` and returns a `TokenPairOut`.
  - Recovery: `/auth/recovery/code` is removed; `POST /api/auth/recovery {new_phone, old_phone, details}` now requires a **verified session on the new number** (the person registers it first and the team checks it on WhatsApp) instead of a code; the old-number warning SMS is dropped.
  - Partner requests: `/partner-requests/code` is removed and `/partner-requests` no longer takes `code`.
  - `ensure_role` and `link_merchant`, when they create a user or the user has no password: set a random unusable hash, `must_change_password=True`, and `open_check(kind="reset_password")`. The cashier SMS in `staff.py` and the other `_notify` SMS calls are removed.

- [ ] **Step 1: Write the failing tests:** `test_change_number_needs_the_password_and_the_code_on_the_new_number`, `test_recovery_needs_a_verified_new_number`, `test_partner_request_without_code`, `test_new_merchant_login_waits_in_the_team_queue` (an open `reset_password` check exists after `grant_role`), `test_new_cashier_login_waits_in_the_team_queue`, `test_existing_customer_made_merchant_keeps_their_password`.
- [ ] **Step 2: Run** those files → FAIL.
- [ ] **Step 3: Implement**, replacing each file's `_sign_in` helper with `tests/helpers.sign_in`.
- [ ] **Step 4: Run** `pytest -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Move number changes, recovery and new logins to WhatsApp checks"`

### Task 7: Admin accounts API

**Files:**
- Create: `app/api/admin_accounts.py`, `tests/test_admin_accounts.py`
- Modify: `app/main.py` (router under `/api/admin/accounts`)

**Interfaces:**
- Consumes: Task 2 services, `require_role("admin")`, `revoke_all_sessions`.
- Produces (every route writes one `AdminAction` row: `admin_user_id`, `action` = the route's verb, `user_id`, `check_id`, `ip` from `request.client.host`):
  - `GET /checks?kind=verify_number|reset_password|change_number` → `[{id, kind, app ("customer"|"merchant"), phone_masked, created_at, sent_at, team_created (bool: opened by ensure_role/link_merchant)}]`, open checks only, oldest first
  - `POST /checks/{id}/send` → `{"url": "https://wa.me/..."}`; `POST /checks/{id}/refuse` → 204
  - `GET /users?phone=` → `{id, phone_masked, roles, disabled, verified, last_login_at}` or 404
  - `POST /users/{id}/suspend`, `/restore`, `/sign-out` → 204; `POST /users/{id}/reset-password` → `{"check_id": int}`

- [ ] **Step 1: Write the failing tests:** `test_only_admins_reach_these_routes` (customer, merchant and agent tokens → 403), `test_send_returns_a_whatsapp_link_and_logs_it`, `test_refused_number_is_shown_to_the_user` (`/auth/me` after refusal → `verified: false` and a new field `number_refused: true`; add it to `/auth/me`), `test_lists_mask_the_number`, `test_suspend_and_sign_out`, `test_reset_password_opens_a_check`.
- [ ] **Step 2: Run** `pytest tests/test_admin_accounts.py -q` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest -q` → PASS.
- [ ] **Step 5: Commit** `git commit -m "Admin routes for WhatsApp checks and accounts"`

### Task 8: Remove SMS and the old routes

**Files:**
- Delete: `app/services/otp_sender.py`, `app/api/orange_sms.py`, `tests/test_otp_sender.py`, `tests/test_orange_delivery.py`, `tests/test_auth_otp.py` (its still-relevant cases — disabled user, refresh rotation and reuse, logout, roles — move to `tests/test_password_auth.py`)
- Modify: `app/core/otp.py` (delete; imports point to `core/tokens.py`), `app/api/auth.py` (remove `send_code`, `check_code`, `test_numbers`, the demo `/token` route, `OtpChallenge` use; add the 410 routes), `app/main.py` (no sender check at startup, no Orange router), `app/services/purge.py` (purge `account_checks` done/refused older than 30 days instead of `otp_challenges`), `app/models.py` (drop `OtpChallenge`; migration `0030_drop_otp_challenges`), `app/seed.py`, `app/metrics.py` (drop OTP metrics), `tests/test_purge.py`, `tests/test_account_delete.py`, `tests/test_admin_api.py`, `tests/acceptance/conftest.py`, `../render.yaml`, `../render.production.yaml`

**Interfaces:**
- Produces:
  - `POST /api/auth/otp/request` and `/api/auth/otp/verify` → 410 `{"detail": "Mettez a jour l'application Fidelia pour vous connecter."}`
  - Seed (non-production only, refused when `FIDELIA_ENV=production`): `DEV_*_PHONE` users get password `fidelia2026`, verified: `+2250700000001` customer, `…02` merchant, `…03` cashier, `…04` agent, `…09` admin.

- [ ] **Step 1: Write the failing tests:** `test_old_otp_routes_ask_for_an_update` (Review Focus 2), `test_seed_accounts_sign_in_with_their_password`, `test_seed_passwords_are_refused_in_production`.
- [ ] **Step 2: Run** them → FAIL.
- [ ] **Step 3: Remove and rewire**; replace the remaining `_sign_in` helpers with `tests/helpers.sign_in`; delete the `OTP_*`, `ORANGE_*`, `AT_*` and `TEST_OTP_NUMBERS` entries from both Render files.
- [ ] **Step 4: Verify:** `pytest -q` → PASS; `grep -rn "otp_sender\|orange_sms\|OTP_SENDER\|TEST_OTP_NUMBERS\|OtpChallenge" app tests ../render*.yaml` → no output; `alembic upgrade head` on a scratch database → OK.
- [ ] **Step 5: Commit** `git commit -m "Remove SMS codes and the Orange integration"`

### Task 9: Backend docs and merge

**Files:**
- Create: `app/scripts/set_password.py` (`python -m app.scripts.set_password +225…`: how the first admin gets a password; prompts twice, refuses weak passwords, marks the number verified)
- Modify: `fidelia-docs/docs/technical/TECHNICAL-GUIDE.md` (Sign-in section: the new routes, checks, seed passwords, the script), `../CHANGELOG.md`
- Test: `tests/test_set_password_script.py`

- [ ] **Step 1: Write the failing test** `test_script_sets_a_verified_password` (calls the script's `main(["+2250700000099"], input=...)`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** the script. **Step 4: Run** `pytest -q` → PASS.
- [ ] **Step 5: Update the docs and changelog; commit** `git commit -m "Document password sign-in"`; push the branch, merge into `integration`, check the test API deploy answers `POST /api/auth/login` with the seed admin.
