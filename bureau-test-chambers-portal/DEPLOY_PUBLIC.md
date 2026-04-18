# Make The Portal Public

This is the fastest safe path to get the Bureau account portal online for other people.

## Recommended Host

Use Render for the first public launch.

Why:

- the project already includes a `render.yaml`
- the portal is a single Python process with static files
- Render gives you HTTPS without extra reverse-proxy setup
- the portal needs persistent storage for accounts, sessions, moderation logs, and published levels

## Before You Deploy

1. Put the folder in its own Git repository, or push it as a clean subproject repository:
   `/Users/jessejames/Documents/Codex Apps/bureau-test-chambers-portal`
2. Make sure the repo includes:
   - `server.py`
   - `index.html`
   - `app.js`
   - `styles.css`
   - `render.yaml`
   - `downloads/` if you want the beta download to appear on day one
3. Pick a strong director password. Do not reuse a password from anywhere else.

## Render Setup

1. Create a new Render account and connect the repository.
2. Choose the Blueprint deploy flow so Render reads `render.yaml`.
3. Let Render create the `bureau-account-portal` web service.
4. Keep the persistent disk attached at:
   `/var/data/bureau-account-portal`
5. Set these required environment values in Render:
   - `BUREAU_PUBLIC_BASE_URL=https://your-public-domain`
   - `BUREAU_DIRECTOR_PASSWORD=<your real password>`
6. Leave these production values enabled:
   - `BUREAU_ENV=production`
   - `BUREAU_ENABLE_DEV_DEFAULTS=0`
   - `BUREAU_REQUIRE_HTTPS=1`
   - `BUREAU_PORTAL_HOST=0.0.0.0`

## Domain

You can launch in either of these ways:

- Fastest: use the default Render domain first.
- Cleaner: attach your own domain such as `accounts.yourgame.com`.

If you use a custom domain, update:

- `BUREAU_PUBLIC_BASE_URL`

to the final HTTPS URL.

## First Public Checks

After the deploy finishes, verify these URLs:

- `https://your-domain/`
- `https://your-domain/healthz`
- `https://your-domain/api/levels`

Expected results:

- `/` loads the account portal page
- `/healthz` returns a healthy JSON response
- `/api/levels` returns a JSON payload, even if the level list is empty

## Game Connection

After the website is live, point the game to the same public portal URL from the account/settings area.

If the game still points at `127.0.0.1` or `localhost`, other players will never reach the public site.

## Important Notes

- This portal is not ready for a free-tier disposable host because live accounts need persistent storage.
- Do not publish your local `data/accounts.db`.
- Do not keep the default director password.
- If you want password reset emails later, that will need a separate mail provider integration. The current portal does not send mail by itself.

## Quick Summary

The shortest path is:

1. push the portal as its own repo
2. deploy the repo to Render with the included `render.yaml`
3. set `BUREAU_PUBLIC_BASE_URL`
4. set a real `BUREAU_DIRECTOR_PASSWORD`
5. point the game at the public URL
