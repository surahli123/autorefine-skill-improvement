# HANDOVER

## Goal
Refactor the auth middleware to support API-key auth alongside JWT.

## Failed approaches (don't repeat)
- Tried adding the API-key check inside the existing JWT middleware. Failed — it short-circuited JWT requests. Error: `401 Unauthorized` on valid JWTs, because the key check ran first and returned early.

## Code context
- `authenticate(req) -> {userId, scopes}` — current JWT-only entrypoint, called by every route.
- `verifyJwt(token) -> claims | throws` — unchanged.
- Planned: `verifyApiKey(key) -> {userId, scopes} | null` — not written yet.
- Middleware order: `cors -> authenticate -> rateLimit -> router`.

## Setup / env
- `JWT_SECRET` (existing). A new `API_KEYS_TABLE` DynamoDB name will be needed (redacted).

## Warnings / gotchas
- Scopes from API keys must map to the same scope strings JWT uses, or RBAC checks silently diverge.
- Don't log raw API keys.
