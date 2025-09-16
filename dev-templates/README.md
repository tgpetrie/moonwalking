# Developer templates

This folder contains tracked templates for developer environment files.

Usage

- To create your local frontend env file from the template (safe, non-destructive):

  cp dev-templates/frontend.env.local.template frontend/.env.local

  Or run the project setup script which will copy the template if your local file is missing:

  ./setup_dev.sh

Force overwrite

- If you intentionally want to overwrite your local `frontend/.env.local` from scripts, set the environment variable `FORCE_ENV_WRITE=1` when running `./start_local.sh` or `./start_orchestrator_background.sh`.

Toggle WebSocket vs REST fallback

- The frontend reads `VITE_DISABLE_WS` at build/start time.
  - `VITE_DISABLE_WS=false` (default) enables WebSockets when available.
  - `VITE_DISABLE_WS=true` disables WebSockets and forces REST polling/fallback.

- To test REST-only behavior, add `VITE_DISABLE_WS=true` to your local `frontend/.env.local` and restart the dev server.

Notes

- `frontend/.env.local` is intentionally gitignored and per-developer. Do not commit personal secrets or machine-specific overrides.

