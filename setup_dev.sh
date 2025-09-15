#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
cd "$here"

# Determine Python (prefer 3.12). Honor $PYTHON if set.
if [ -n "${PYTHON:-}" ] && command -v "$PYTHON" >/dev/null 2>&1; then
  PY="$PYTHON"
else
  for p in python3.12 python3.11 python3 python; do
    if command -v "$p" >/dev/null 2>&1; then PY="$p"; break; fi
  done
fi
if [ -z "${PY:-}" ]; then
  echo "[setup] ERROR: no python found (tried: python3.12 python3.11 python3 python)." >&2
  echo "        Install Python 3.12 (pyenv or Homebrew) and re-run." >&2
  exit 1
fi

PYVER=$($PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[setup] python: $PY ($PYVER)"
if $PY -c 'import sys; sys.exit(0 if (sys.version_info.major==3 and sys.version_info.minor<=12) else 1)'; then
  : # ok <= 3.12
else
  echo "[setup] WARNING: Python $PYVER detected; pydantic-core via PyO3 may not support >3.12 in this repo." >&2
  echo "         Prefer a 3.12 venv. Workaround (use with caution): export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1" >&2
fi

VENV=.venv
if [ ! -d "$VENV" ]; then
  echo "[setup] creating venv: $PY -m venv $VENV"
  "$PY" -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "[setup] upgrading pip/build tools"
pip install --upgrade pip setuptools wheel

echo "[setup] installing backend requirements"
if [ -f backend/requirements.txt ]; then
  if ! pip install -r backend/requirements.txt; then
    echo "[setup] pip install failed. If the error is about pyo3/pydantic-core on Python 3.13," >&2
    echo "         create a Python 3.12 venv and re-run, or export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 and retry." >&2
    exit 1
  fi
else
  echo "[setup] no backend/requirements.txt; skipping"
fi

if [ -d frontend ]; then
  echo "[setup] installing frontend deps"
  pushd frontend >/dev/null
  npm install --no-fund --no-audit
  popd >/dev/null
fi

echo "[setup] ensuring frontend/.env.local"
mkdir -p frontend
if [ ! -f frontend/.env.local ]; then
  cat > frontend/.env.local <<'EOF'
# Vite local env
VITE_API_URL=/api
EOF
fi

echo "[setup] done."