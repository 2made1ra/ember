# Supabase Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real email/password Supabase authentication to ARGUS and require authenticated users for current application APIs.

**Architecture:** React owns Supabase email/password session state and sends the access token through the existing `fetchJson` helper. FastAPI protects all application endpoints except `/api/health` by validating bearer tokens with the Supabase Auth `/auth/v1/user` endpoint.

**Tech Stack:** React, Vite, `@supabase/supabase-js`, FastAPI, httpx, Python unittest, Node test runner.

---

## File Structure

- Create `frontend/src/supabaseClient.js`: build and export the browser Supabase client from Vite env vars.
- Create `backend/app/auth.py`: validate bearer credentials against Supabase Auth and expose a FastAPI dependency.
- Modify `frontend/src/App.jsx`: add auth gate, session state, logout button, and authenticated API requests.
- Modify `frontend/src/styles.css`: style the auth gate and logout controls.
- Modify `frontend/package.json` and lockfile: add `@supabase/supabase-js`.
- Modify `backend/app/main.py`: apply `Depends(require_user)` to protected endpoints.
- Modify `backend/app/config.py`: read Supabase URL/key.
- Modify `.env.example` and `README.md`: document Supabase setup.
- Modify `backend/tests/test_api.py`, `backend/tests/test_config.py`, and `frontend/tests/smoke.test.mjs`: add focused regression coverage.

## Tasks

### Task 1: Backend Auth Tests And Config

**Files:**
- Modify: `backend/tests/test_config.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/app/config.py`
- Create: `backend/app/auth.py`
- Modify: `backend/app/main.py`

- [ ] Write failing config tests for `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`.
- [ ] Write failing API tests for missing, invalid, and valid bearer tokens.
- [ ] Run backend tests and confirm the new tests fail because auth is not implemented.
- [ ] Add `supabase_url` and `supabase_publishable_key` fields to `Settings`.
- [ ] Add `require_user` dependency that extracts bearer credentials and validates them through Supabase Auth `/auth/v1/user`.
- [ ] Attach `Depends(require_user)` to protected FastAPI endpoints.
- [ ] Run backend tests and confirm they pass.

### Task 2: Frontend Auth Tests And Client

**Files:**
- Modify: `frontend/tests/smoke.test.mjs`
- Create: `frontend/src/supabaseClient.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/package.json`

- [ ] Write failing frontend smoke assertions for Supabase client wiring, auth form labels, logout, and authorization headers.
- [ ] Run `npm --prefix frontend test` and confirm the new assertions fail.
- [ ] Install `@supabase/supabase-js`.
- [ ] Create the Supabase client module with `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`.
- [ ] Add auth session state and sign in/sign up/logout handlers to `App.jsx`.
- [ ] Pass the current token into all existing API calls through `fetchJson`.
- [ ] Add auth screen and logout styles.
- [ ] Run frontend tests and build.

### Task 3: Docs And Final Verification

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] Add Supabase env vars to `.env.example`.
- [ ] Update README setup instructions with Supabase Auth requirements.
- [ ] Run backend tests.
- [ ] Run frontend tests.
- [ ] Run frontend build.
- [ ] Report exact verification results and mention that no commit was created because this folder is not a git repository.
