BHABIT / Moonwalking — Local Dev & Cloudflare

Note: backend native extensions (pydantic-core / pyo3) may require Python 3.12 to build reliably.
If you have Python 3.13 and see build errors, either create a Python 3.12 venv or set
`PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` as a temporary workaround before running `pip install`.

One-time setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install
```

Quick start (hydration + env files)

```bash
./setup_dev.sh
```

    •	Creates/updates .venv
    •	Installs frontend deps
    •	Writes env files (frontend/.env.local, etc.)

Daily run (local API + Vite)

```bash
./start_local.sh
```

    •	Auto-picks a free backend port
    •	Writes frontend/.env.local
    •	Starts Flask API + Vite on port 3100
    •	Open http://127.0.0.1:3100 (backend URL is printed)

Full Cloudflare-style stack (Pages + Durable Object, locally)

```bash
./start_cloudflare.sh
```

    •	Kills stale wrangler processes
    •	Boots DO on 8787
    •	Launches Pages dev on 8789 with functions/ routed
    •	Verify: ./status.sh and curl http://127.0.0.1:8789/api/server-info

Note: start_app.sh currently contains JSX (not a shell script). Use start_local.sh or start_cloudflare.sh.

Deploy Web/Desktop to Cloudflare Pages

```bash
cd frontend
npm run build
wrangler pages deploy dist --config ../wrangler.pages.toml --project-name moonwalking
```

Then in Cloudflare Dashboard → Pages → moonwalking → Settings → Environment Variables set:
    • BACKEND_ORIGIN → public Worker URL (or Render fallback https://moonwalker.onrender.com)
    • VITE_API_URL → (recommended) relative path if calling Pages Functions

Ensure functions/ is included in deploy via wrangler.pages.toml.

Backend / Worker (shared web + mobile API)
    • Local dev (root): npx wrangler dev -c wrangler.worker.toml --local --persist-to .wrangler/state
    • Production: npx wrangler deploy --config wrangler.worker.toml
    • Attach KV/Queues in Dashboard (ensure existing IDs match your config)
    • Set worker env vars (CRON_SECRET, etc.)

Mobile Monorepo (moonwalking_mobile/)

```bash
cd moonwalking_mobile
npm install                        # bootstraps workspaces
npm run dev:worker                 # worker API (8787 default)
API_BASE=http://127.0.0.1:8787 npm run dev:mobile   # Expo / Metro
```

    • Scan the QR in Expo Go or run npm run ios / npm run android
    • Confirm API in Metro logs ([mobile.api] baseURL) and wrangler logs

Deploy the Mobile API Worker

```bash
cd moonwalking_mobile/backend-workers/moonwalking-worker
npm install
npm run deploy
```

    • Note the Worker URL: https://<subdomain>.workers.dev
    • Supply it to Expo builds:
    • apps/mobile/.env.production: EXPO_PUBLIC_API_BASE=https://<worker-url>
    • or set in EAS env
    • The Settings screen reflects Constants.expoConfig.extra.API_BASE

Cloudflare Pages + Worker Integration
    • Update Pages vars (BACKEND_ORIGIN, VITE_API_URL) to point the desktop site to your chosen backend
    • Update Expo config (API_BASE) for mobile
    • Single-origin option: route both web + mobile to one Worker; ensure /api/mobile/* and /api/component/* endpoints exist

Verifications

```bash
curl https://<pages-domain>/api/server-info     # web
wrangler tail                                   # each worker
# Mobile: expo publish → open on device → check watchlist/learn/notifications
```

Caveats / Follow-ups
    • Fix or remove the JSX-filled start_app.sh to avoid confusion
    • Ensure KV namespace MW_KV and DO class WatchlistDO exist/attached
    • Keep secrets in Cloudflare Secret Manager (not in config)
    • wrangler login / gh auth login before deploying
