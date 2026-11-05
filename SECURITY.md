# MVP security and session model

Verified email login is now the default; see [EMAIL_LOGIN_SETUP.md](EMAIL_LOGIN_SETUP.md) for provider configuration and current account behavior. The guest model described below remains available for offline development and existing-session upgrades. New guest creation requires `ALLOW_GUEST_LOGIN=true`; it is disabled by default. Verified accounts can recover access with a fresh email code after losing their session.

## Audit findings addressed

The prototype allowed a known handle to sign in without proof of identity. Client-controlled `X-User-Id` headers selected owners, submission retrieval and generation had no authentication, save/unsave permitted missing credentials, and `/media` publicly served room photos. Internal file paths were returned in API responses. Upload MIME headers were trusted and file size was unbounded. Full AI requests, including user notes, were logged.

These paths now require authenticated ownership. Catalog items and catalog photos remain public. The health check and API schema/documentation remain public; their availability does not grant access to private resources.

## Guest sessions

`POST /api/login` accepts a new display handle (3–20 ASCII letters, digits, underscores; trimmed and lowercased). It creates a guest account and returns `id`, `handle`, `created_at`, `token`, and `expires_at`. Duplicate handles receive 409, including legacy handles. Entering an existing handle never recovers an account.

The token is 32 cryptographically random bytes encoded as URL-safe text. It is an opaque bearer credential, not a signed JWT; only its SHA-256 hash is stored server-side. Its entropy makes signatures and password hashing unnecessary here. Every protected request sends `Authorization: Bearer <token>`. Tokens never appear in query strings or image URLs. `GET /api/me` validates a session; `POST /api/logout` marks it revoked. New sessions expire after `SESSION_HOURS` (default 24).

The frontend uses sessionStorage with an in-memory fallback. Reloading the tab keeps access; closing the tab, signing out, or token expiry ends normal access. Browser restore/duplication may preserve sessionStorage, so server expiry remains authoritative. Guest sessions have no recovery mechanism. Saved designs survive in storage but cannot be reopened after the credential is lost. Persistent accounts and verified email login are a future step. JavaScript storage is exposed to script injection; this MVP is not a substitute for a reviewed persistent authentication system.

## Protected routes

| Route | Access |
| --- | --- |
| `POST /api/login` | Public, new guest creation, rate limited |
| `GET /api/me`, `POST /api/logout` | Valid session |
| `POST /api/submissions` | Valid session; owner assigned by server |
| `GET /api/submissions/{id}` | Submission owner |
| `POST /api/generate/{id}` | Submission owner |
| `GET /api/designs` | Only current user's saved designs |
| `POST`, `DELETE /api/designs/{id}/save` | Submission owner |
| `GET /api/media/{id}/room`, `/generated` | Submission owner |
| `/api/catalogue`, `/catalogue-images/*`, `/api/health` | Public |

Missing, invalid, revoked, or expired sessions receive 401. Missing resources and resources belonging to another user both receive 404. `X-User-Id` is ignored. Room and generated image response fields contain protected API paths, not disk paths. The frontend fetches images with an authorization header and renders local blob URLs, revoking them on unmount. Private responses use `Cache-Control: no-store`.

Uploads must be valid JPEG, PNG, or WebP content matching the declared MIME type. User filenames are ignored. Images are decoded, orientation corrected, metadata stripped, and encoded as JPEG with random filenames. Defaults: 8 MiB file limit and 20 million pixels. Request bodies are bounded before multipart parsing, including requests without Content-Length (upload limit plus 64 KiB form overhead; other write requests 64 KiB). Private media paths are checked against the upload root, including resolved symlinks.

## Existing data and migrations

Startup adds sessions and rate-attempt tables/indexes without removing existing rows or files. Legacy users, submissions, and photos are preserved. Old handles and ownerless submissions cannot be claimed through the public API. Any recovery requires a separate, verified administrator migration; do not assign legacy data based only on a handle. Existing localStorage user records are ignored. Deploy frontend and backend together because old clients do not understand tokens or protected media paths.

## Configuration and deployment

Copy backend `.env.example` for development; set `FRONTEND_ORIGINS` and frontend `VITE_API_BASE_URL` to the actual deployment origins. CORS only permits listed origins unless `DEVELOPMENT_CORS=true` explicitly enables arbitrary localhost ports. Keep this option false publicly. Use HTTPS so bearer tokens cannot be intercepted. No signing key or paid authentication service is required.

`LOGIN_ATTEMPTS_PER_HOUR` defaults to 20 per connection IP; `UPLOADS_PER_HOUR` to 30 per account; `GENERATIONS_PER_HOUR` to 10 per account. Limits use shared SQLite transactions across workers; repeated requests for an already generated result do not consume another generation slot. Failed duplicate-handle attempts still count. Limit failures return 429 with Retry-After. Configure the reverse proxy's trusted client IP handling correctly; arbitrary forwarded headers are not trusted by application code. Users behind a shared proxy may share a login allowance. These basic limits do not provide a global AI spend cap or stop an attacker creating multiple accounts/IPs.

Keep `DEBUG_AI_LOGGING=false`; provider errors returned to clients are sanitized. Uploaded photos and user inputs still go to the configured AI provider when Gemini is enabled. This work does not establish a privacy notice, deletion/retention automation, catalog licensing, object storage, or a production database. Rate-attempt rows are retained; schedule reviewed archival/cleanup before long-term use. Existing data and files have not been deleted.

## Verification

Run `python -m pip install -r requirements-dev.txt` and `python -m pytest -q` from backend. Tests isolate data/uploads in a temporary directory and use mock AI, covering missing credentials, forged user IDs, cross-user reads/generation/save/unsave/media, session hashing/expiry/revocation, legacy data, MIME/content and upload limits, metadata, filesystem containment, rate limits, and CORS.

From frontend, run `npm install`, `npm run build`, and `npm run lint`. Use dependencies installed for your OS; the included `.venv` and `node_modules` may originate on another machine. Manually verify new guest creation, generation and image loading, save, reload, logout, and attempted duplicate-handle login before deployment.

Verified on October 11, 2026: 23 backend tests passed with mock AI; TypeScript compilation, production Vite build, and application-source lint checks passed. An automated headless Chrome smoke test passed guest creation, photo upload, generation, protected blob image rendering, saving, reload persistence, logout revocation, duplicate-handle rejection, and redirect after server revocation. Tests used an isolated temporary database, uploads, and macOS dependency installation because the existing dependency folders originated on Windows. The source check passed with the existing TypeScript dependency; the isolated build used versions permitted by package.json. The backend suite reports one upstream Starlette/AnyIO deprecation warning.
