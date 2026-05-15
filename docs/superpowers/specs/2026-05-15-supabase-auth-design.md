# Supabase Email Password Auth Design

## Context

ARGUS is a local MVP with a React/Vite frontend and a FastAPI backend. The frontend talks to the backend through the Vite `/api` proxy. The backend currently exposes catalog upload, chat, chat reset, and semantic search endpoints without user authentication.

The first Supabase integration step is email/password authentication only. SQL-backed product features are out of scope for this step.

## Selected Approach

Use Supabase Auth in the frontend for registration, login, logout, and session persistence. The frontend sends the current Supabase access token to the FastAPI backend on every protected API request.

The backend verifies each protected request by calling the Supabase Auth `/auth/v1/user` endpoint with the bearer token. This keeps the first implementation compatible with Supabase projects using legacy symmetric JWT signing and newer JWT configurations. A later optimization can replace this remote check with JWKS verification if the project uses asymmetric signing.

## Configuration

Add these environment variables:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`

The frontend uses the `VITE_` variables. The backend uses the non-`VITE_` variables to validate tokens against the Supabase Auth endpoint.

## Frontend Behavior

When no Supabase session exists, show an authentication screen before the current ARGUS app. The screen supports:

- email/password sign in
- email/password sign up
- inline error display
- loading state while Supabase Auth calls are pending

When a session exists, render the current ARGUS workspace. The sidebar/footer user area shows the authenticated email and a logout button.

All API requests go through the existing `fetchJson` helper. It attaches `Authorization: Bearer <access_token>` when a session token is available.

## Backend Behavior

`/api/health` remains public.

These endpoints require a valid Supabase access token:

- `GET /api/catalog/status`
- `POST /api/catalog/upload`
- `POST /api/chat`
- `POST /api/chat/reset`
- `POST /api/search`

Missing or malformed credentials return `401`. Tokens rejected by Supabase also return `401`.

## Testing

Backend tests cover:

- public health endpoint remains public
- protected endpoint rejects missing token
- protected endpoint accepts a token validated by a mocked Supabase Auth response
- invalid token returns `401`
- config reads Supabase URL and publishable key

Frontend smoke tests cover:

- auth UI strings exist
- Supabase client is wired
- API helper sends authorization headers
- logout/sign in/sign up flows are represented in source

## Out of Scope

- OAuth providers
- magic links
- Supabase Postgres tables
- Row Level Security policies
- per-user catalog ownership
- server-side Supabase service role usage
