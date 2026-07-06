#!/usr/bin/env bash
# Build the Moonwalking app for a single-box home-server deploy.
# Run from anywhere; operates on the repo this script lives in.
# Safe to re-run (idempotent): rebuilds venv deps and the frontend bundle.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "[setup] repo: $REPO_ROOT"

# --- python venv + backend deps ---
if [ ! -d .venv ]; then
  echo "[setup] creating .venv"
  python3 -m venv .venv
fi
./.venv/bin/pip install --upgrade pip -q
echo "[setup] installing backend requirements"
./.venv/bin/pip install -r backend/requirements.txt -q

# --- frontend build (same-origin API) ---
# Force the API base vars empty so the bundle uses same-origin requests.
# Otherwise a stale frontend/.env.local written by start_app.sh would bake
# a http://127.0.0.1:<port> URL into the production bundle.
echo "[setup] building frontend (same-origin API base)"
cd frontend
if [ ! -d node_modules ]; then
  npm ci
fi
VITE_API_BASE= VITE_API_BASE_URL= VITE_API_URL= npm run build
cd "$REPO_ROOT"

# --- env file ---
ENV_FILE="deploy/homeserver/.env"
if [ ! -f "$ENV_FILE" ]; then
  cp deploy/homeserver/env.example "$ENV_FILE"
  SECRET="$(./.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')"
  # Fill SECRET_KEY in place (BSD/GNU sed compatible via temp file)
  sed "s|^SECRET_KEY=$|SECRET_KEY=${SECRET}|" "$ENV_FILE" > "${ENV_FILE}.tmp"
  mv "${ENV_FILE}.tmp" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "[setup] wrote $ENV_FILE with a generated SECRET_KEY (review the other values)"
else
  echo "[setup] $ENV_FILE already exists; leaving it untouched"
fi

echo
echo "[setup] done. Next steps (see deploy/homeserver/README.md):"
echo "  1. Review $ENV_FILE (WATCHLIST_DB_PATH location + backups)"
echo "  2. sudo cp deploy/homeserver/moonwalking-*.service /etc/systemd/system/"
echo "     (edit User/paths inside if the repo is not at /opt/moonwalking)"
echo "  3. sudo systemctl daemon-reload && sudo systemctl enable --now moonwalking-backend moonwalking-sentiment"
echo "  4. tailscale serve --bg http://127.0.0.1:5003"
