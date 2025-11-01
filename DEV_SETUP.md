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

Secrets & Models — quick workflow
--------------------------------

Keep secrets out of the repository and prefer a per-project `.env` + a launcher so GUI apps inherit values.

1) Per-project `.env` (recommended)

    - Create `.env` from `.env.example` and edit locally:

        ```bash
        cp .env.example .env
        # edit .env with real keys (do not commit)
        chmod 600 .env
        ```

    - Launch VS Code so it inherits the env vars (launcher included in repo):

        ```bash
        ./scripts/launch-vscode-with-env.sh .
        ```

2) Pre-commit scanning (detect-secrets)

    - Install and create a baseline to avoid noisy failures on existing non-secret files:

        ```bash
        pip install --user detect-secrets pre-commit
        detect-secrets scan > .secrets.baseline
        git add .secrets.baseline
        git commit -m "chore: add detect-secrets baseline"
        pre-commit install
        ```

3) Model pulls and pruning (disk conscious on 8 GB machines)

    - Prefer small models for default work: `phi3:mini`, `qwen2.5-coder:1.5b-base`, `qwen3:4b`.
    - Avoid running Llama3-8B by default on an 8 GB Air; use cloud for heavy passes.
    - Remove unused models:

        ```bash
        ollama list
        ollama rm <model-name>
        ```

4) Quick sanity checks

    - Ollama reachable:
        ```bash
        curl -sS http://127.0.0.1:11434/api/tags | jq .
        ```
    - Continue YAML parse test:
        ```bash
        python3 - <<'PY'
        import pathlib, yaml
        p = pathlib.Path.cwd()/'.continue'/'config.yaml'
        if not p.exists(): p = pathlib.Path.home()/'.continue'/'config.yaml'
        yaml.safe_load(p.read_text())
        print('YAML OK:', p)
        PY
        ```

These small steps keep your local dev fast, safe, and predictable.
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

Offline / fixture mode (quick local development without internet)
-------------------------------------------------------------

If your development machine has restricted egress or you prefer a deterministic
dataset while iterating on frontend UI, the backend can serve representative
fixture payloads for the main component endpoints (gainers/losers tables and
banner streams).

Start the backend in fixtures mode:

```bash
./stop_local.sh
USE_FIXTURES=1 ./start_local.sh
```

This will cause the backend to return sample payloads for endpoints such as:

    - /api/component/gainers-table-1min
    - /api/component/gainers-table-3min
    - /api/component/losers-table-3min
    - /api/one-hour-price

You can verify by curling the endpoints and looking for a `mode: "fixtures"` or
well-formed JSON with non-empty `data` arrays.

To run with live data, ensure the backend can reach the external APIs (unblock
egress or configure HTTPS_PROXY) and run `./start_local.sh` normally.

Seeded 1-minute data (dev-only)
--------------------------------

If the 1-minute gainers table is empty on cold start you can enable a small
dev-only seed so the UI shows realistic rows immediately without enabling the
full fixtures mode.

Enable it like this:

```bash
USE_1MIN_SEED=1 ./start_local.sh
```

This reads `backend/fixtures/top_movers_3m.json`, maps a few entries into the
1-minute endpoint response, and returns them without writing to persistent
storage. The default is OFF; do not enable this in CI or production.
