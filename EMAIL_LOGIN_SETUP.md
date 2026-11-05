# Verified email sign-in setup

DormWrapper now uses Supabase Auth's email one-time-code flow. New and returning users enter an email address and a six-digit code. Supabase generates, delivers, expires, and consumes the code. The backend checks the verified email and Supabase user ID before creating a private DormWrapper session. Returning users regain access to the same saved designs, including on a different browser or device.

## Configure Supabase

1. Create or select a Supabase project. You can use Auth without moving the app's current SQLite database into Supabase.
2. In Authentication's sign-in/provider settings, enable Email and new user signups. Keep email confirmation enabled. Configure six-digit codes; a short expiry such as 10 minutes is suitable for this form.
3. In Authentication > Email Templates, edit the Magic Link template to display the `{{ .Token }}` value. If a separate Confirm Signup template is present, use the code there too so the first sign-in works. Do not leave the default link-only template enabled for this UI.
4. Configure custom SMTP in Supabase Auth using your email provider's host, port, username, password, verified sender address, and sender name. Supabase's built-in mail service only sends to project team addresses and is not suitable for public signups. The SMTP credentials belong in Supabase's dashboard, not the frontend or this repository.
5. From the Supabase project settings, copy its HTTPS project URL and publishable API key (a legacy anon key also works). Do not use a service-role/admin key. No administrative permissions are needed by this integration.
6. Set these values in backend `.env` locally or backend hosting environment variables:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
VERIFIED_SESSION_HOURS=168
ALLOW_GUEST_LOGIN=false
```

Keep these values out of Git. This integration makes provider requests on the backend; no Supabase values are needed in frontend `.env`. The frontend still needs `VITE_API_BASE_URL`. Restart the backend after changing its environment.

The email template can use:

```html
<h2>Your DormWrapper sign-in code</h2>
<p>Enter this code in DormWrapper: <strong>{{ .Token }}</strong></p>
<p>If you did not request this code, you can ignore this email.</p>
```

This code-based flow does not need a magic-link callback route or URL tokens. Supabase's Auth REST endpoints are `/auth/v1/otp` and `/auth/v1/verify`. Configure the provider's sending quotas and protections for your public traffic; application limits also apply.

## Application behavior

`POST /api/auth/request-code` takes `{ "email": "you@example.com" }`. It returns a generic check-your-inbox message with no session credential. `POST /api/auth/verify-code` takes `{ "email": "you@example.com", "code": "123456" }`. Only successful provider verification of a confirmed, matching email creates a session. Provider access and refresh tokens are never returned to the browser or persisted.

The app keeps the existing hashed opaque bearer-token model, ownership checks, and protected images. Verified sessions expire after seven days by default; logout revokes the session. SessionStorage retains login in the tab. After closing the tab or expiry, users can sign in with a fresh email code and recover their saved designs. It does not provide automatic cross-tab login or refresh sessions.

Accounts are keyed by Supabase user ID, not an unverified input email. A generated display handle avoids asking new users to choose a unique name. Changing a verified email upstream preserves the same account ID. Deleting and recreating a provider identity does not silently claim an old account with the same email. Replacing the configured Supabase project requires a planned identity migration.

Active guest sessions can select **Verify email to keep designs**. Proof of both the current guest session and the verified email preserves those designs. If the email already owns an account, the guest's submissions are transferred to it and the old guest tokens revoked. Guest rows and files remain preserved. Legacy accounts without a usable session cannot be claimed by knowing their handle. New guest creation is disabled by default; `ALLOW_GUEST_LOGIN=true` is only needed for offline guest development and regression tests.

The app issues its own sessions after verification, so disabling a user in Supabase does not immediately revoke an existing DormWrapper token. For an account removal or compromise, revoke the relevant application sessions too. Provider sessions are not used to access application data.

## Rate limits and failures

Request-code attempts have an IP limit (`LOGIN_ATTEMPTS_PER_HOUR`, default 20), per-email limit (`EMAIL_REQUESTS_PER_HOUR`, default 3), and a 60-second per-email cooldown. Verification attempts have an IP limit and per-email limit (`EMAIL_VERIFICATIONS_PER_HOUR`, default 10), including failed attempts. Emails and IPs used for rate keys are hashed. Additional provider rate limits can apply. Errors do not expose provider keys or raw responses. Missing provider configuration returns 503; invalid/expired codes return 400.

## Validate before launch

Install updated backend dependencies, restart the app, and request a code for a real email. Verify that the email contains a code, sign in, generate and save a design, sign out, then sign in again and confirm that the design remains. Repeat with another email and verify that accounts do not share designs. Check wrong, expired, and reused codes and resend throttling.

Automated backend tests mock the provider's HTTP transport, so they make no real email deliveries. Browser verification uses an isolated fake provider and temporary data. Live delivery cannot be confirmed until a real Supabase project and SMTP service are configured.

Verified locally on October 11, 2026: all 35 backend tests passed, TypeScript and production frontend builds passed, and source lint passed. A headless Chrome test passed code request, wrong-code handling, sign-in, generation with private image rendering, save, logout, account/design recovery in a fresh browser context, and reload. Tests used temporary data and a mocked provider; existing application data and files were preserved.

Official references: [Passwordless email sign-in](https://supabase.com/docs/guides/auth/auth-email-passwordless), [SMTP setup and restrictions](https://supabase.com/docs/guides/auth/auth-smtp), [Auth REST API](https://supabase.github.io/auth/).
