# Bureau Test Chambers Web Portal

This folder is the standalone website project for Bureau Test Chambers.

It now lives as its own sibling project outside the Godot game folder. The game uses it for:

- account sign-in
- account syncing
- moderation
- custom level publishing
- community level browsing

## Files

- `server.py`: local and production web server
- `index.html`: portal page shell
- `app.js`: portal client logic
- `styles.css`: portal styles
- `start_portal.command`: one-click local launcher
- `.env.example`: production environment template
- `render.yaml`: Render deployment starter
- `Procfile`: process command for hosts that use Procfiles

## Run Locally

1. Open Terminal.
2. Run:
   `"/Users/jessejames/Documents/Codex Apps/bureau-test-chambers-portal/start_portal.command"`
3. Open:
   [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Make A Portal-Only Copy

Run:

`"/Users/jessejames/Documents/Codex Apps/bureau-test-chambers-portal/export_standalone_portal.command"`

That creates a clean release copy next to this portal project:

- `/Users/jessejames/Documents/Codex Apps/bureau-test-chambers-portal-release`

The export intentionally does not copy your live `accounts.db` or session data.
It creates a fresh `data/` folder so you do not accidentally ship local accounts.

## Make A GitHub-Ready Public Copy

If you want a clean public-upload version of the portal, run:

`"/Users/jessejames/Documents/Codex Apps/bureau-test-chambers-portal/prepare_public_repo.command"`

That creates:

- `/Users/jessejames/Documents/Codex Apps/bureau-test-chambers-portal-release`

The release copy includes:

- the portal app files
- `.env.example`
- `.gitignore`
- `render.yaml`
- `DEPLOY_PUBLIC.md`

and it intentionally leaves `data/` and `downloads/` empty except for placeholder keep-files.

## Production Notes

- Set `BUREAU_ENV=production`
- Set `BUREAU_DATA_DIR` to persistent storage
- Set `BUREAU_PUBLIC_BASE_URL` to your public HTTPS domain
- Set `BUREAU_DIRECTOR_PASSWORD` before going live
- Keep `BUREAU_ENABLE_DEV_DEFAULTS=0`
- Keep `BUREAU_REQUIRE_HTTPS=1`

After deployment, point the game at the public portal URL from the Settings menu,
or export the game with `BUREAU_PORTAL_URL` set.

## Make It Public

The fastest public launch path is Render using the included `render.yaml`.

- See `DEPLOY_PUBLIC.md` for the full checklist
- Use a persistent disk for `/var/data/bureau-account-portal`
- Use a non-default `BUREAU_DIRECTOR_PASSWORD`
- Set `BUREAU_PUBLIC_BASE_URL` to the final HTTPS domain

The Render blueprint in this folder is configured for a paid starter-style service
instead of a disposable free instance because live account data needs persistent storage.
