#!/bin/zsh
set -euo pipefail

# ---------- Paths ----------
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
ROOT="$SCRIPT_DIR"
[[ -d "$SCRIPT_DIR/../backend" ]] && ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV="$ROOT/.venv"

echo "[SETUP] ROOT: $ROOT"
echo "[SETUP] BACKEND_DIR: $BACKEND_DIR"
echo "[SETUP] FRONTEND_DIR: $FRONTEND_DIR"

echo "[SETUP] 🐰 Setting up BHABIT CBMOONERS Development Environment..."
echo "[SETUP] Checking prerequisites..."

# Prefer python3 on systems where `python` may be absent (e.g., macOS)
PYBIN="python"
if ! command -v "$PYBIN" >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    PYBIN="python3"
  else
    echo "[ERROR] python or python3 not found"; exit 1
  fi
fi

command -v node   >/dev/null || { echo "[ERROR] node not found"; exit 1; }
command -v npm    >/dev/null || { echo "[ERROR] npm not found"; exit 1; }
command -v curl   >/dev/null || { echo "[WARN] curl not found in PATH — some checks may be skipped."; }
echo "[SUCCESS] Prerequisites check completed!"
echo "[SETUP] Python version: $($PYBIN -V)"
echo "[SETUP] Node.js version: $(node -v)"

# ---------- Python venv ----------
echo "[SETUP] Ensuring Python virtual environment at $VENV ..."
if [[ ! -d "$VENV" ]]; then
  "$PYBIN" -m venv "$VENV"
  echo "[SUCCESS] Virtual environment created!"
fi
source "$VENV/bin/activate"
echo "[SUCCESS] Virtual environment activated!"
"$PYBIN" -m pip install --disable-pip-version-check -U pip wheel setuptools >/dev/null 2>&1 || true

# ---------- Backend deps ----------
if [[ -f "$BACKEND_DIR/requirements.txt" ]]; then
  REQ="$BACKEND_DIR/requirements.txt"
elif [[ -f "$ROOT/requirements.txt" ]]; then
  REQ="$ROOT/requirements.txt"
else
  echo "[ERROR] requirements.txt not found (looked in $BACKEND_DIR and $ROOT)."
  exit 1
fi
echo "[SETUP] Installing backend dependencies from: $REQ"
"$PYBIN" -m pip install --disable-pip-version-check -r "$REQ"
echo "[SUCCESS] Backend dependencies installed!"

# ---------- Frontend deps ----------
if [[ -d "$FRONTEND_DIR" ]]; then
  echo "[SETUP] Installing frontend deps in $FRONTEND_DIR ..."
  pushd "$FRONTEND_DIR" >/dev/null
  npm install --no-fund --no-audit
  # Ensure needed dev deps for Vite + React + Tailwind v4
  npm install -D @vitejs/plugin-react tailwindcss @tailwindcss/postcss postcss --no-fund --no-audit
  # Optional UI/Icons commonly used by app
  npm install react-icons --no-fund --no-audit || true

  # ---------- Frontend config (idempotent) ----------
  # postcss.config.cjs for Tailwind v4
  cat > postcss.config.cjs <<'EOF'
module.exports = {
  plugins: {
    '@tailwindcss/postcss': {},
  },
};
EOF

  # tailwind v4 minimal config
  cat > tailwind.config.cjs <<'EOF'
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html','./src/**/*.{js,jsx,ts,tsx}'],
  theme: { extend: {} },
  plugins: [],
};
EOF

  # CSS entry
  mkdir -p src
  cat > src/index.css <<'EOF'
@import "tailwindcss";

:root { color-scheme: light dark; }
html, body, #root { height: 100%; margin: 0; }
EOF

  # Ensure main.jsx imports CSS (add at top if missing)
  if [[ -f src/main.jsx ]] && ! grep -q "import './index.css';" src/main.jsx; then
    printf "import './index.css';\n%s" "$(cat src/main.jsx)" > src/main.jsx
  fi

  # Ensure vite.config.js exports a config object
  if [[ ! -f vite.config.js ]] || ! grep -q "defineConfig" vite.config.js; then
    cat > vite.config.js <<'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    host: 'localhost',
  },
})
EOF
  fi
  popd >/dev/null
else
  echo "[WARN] Frontend directory not found; skipping frontend setup."
fi

# ---------- Process cleanup trap ----------
cleanup() {
  echo "[SETUP] 🔻 Shutting down..."
  [[ -n "${BACKEND_PID-}"  ]] && kill $BACKEND_PID  2>/dev/null || true
  [[ -n "${FRONTEND_PID-}" ]] && kill $FRONTEND_PID 2>/dev/null || true
}
trap cleanup EXIT

# ---------- Pick backend port (prefer 5001) ----------
PREFERRED_PORT=5001
PORT=$PREFERRED_PORT
"$PYBIN" - "$PORT" <<'PY'
import socket, sys
port=int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.settimeout(0.2)
    if s.connect_ex(('127.0.0.1', port))==0:
        print('BUSY')
    else:
        print('FREE')
PY
STATUS="$("$PYBIN" - "$PORT" <<'PY'
import socket, sys
port=int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.settimeout(0.2)
    print('BUSY' if s.connect_ex(('127.0.0.1', port))==0 else 'FREE')
PY
)"
if [[ "$STATUS" == "BUSY" ]]; then
  echo "[SETUP] Port $PORT busy, using 5002"
  PORT=5002
fi

# ---------- Start backend ----------
echo "[SETUP] Starting backend on :$PORT ..."
( cd "$BACKEND_DIR" && PORT="$PORT" HOST="0.0.0.0" "$PYBIN" app.py ) &
BACKEND_PID=$!

# ---------- Start frontend ----------
if [[ -d "$FRONTEND_DIR" ]]; then
  echo "[SETUP] Starting frontend dev server (Vite) ..."
  ( cd "$FRONTEND_DIR" && npm run dev ) &
  FRONTEND_PID=$!
fi

echo "[SUCCESS] Backend:  http://127.0.0.1:$PORT"
echo "[SUCCESS] Frontend: http://127.0.0.1:5173 (if frontend started)"
echo "[SETUP] Press Ctrl+C to stop both."
wait