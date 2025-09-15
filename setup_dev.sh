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

needs_recreate=false
if [ -d "$VENV" ]; then
  VENV_PY="$VENV/bin/python"
  if [ -x "$VENV_PY" ]; then
    VENV_MM="$($VENV_PY -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo unknown)"
  else
    VENV_MM="unknown"
  fi
  # Detect any 3.13 artifacts inside the venv (lib or pip shebang)
  if [ -d "$VENV/lib/python3.13" ] || [ -x "$VENV/bin/python3.13" ] || ( [ -f "$VENV/bin/pip" ] && grep -q "python3.13" "$VENV/bin/pip" ); then
    needs_recreate=true
  fi
  # Also recreate if the venv python major.minor isn't 3.12
  if [ "$VENV_MM" != "3.12" ]; then
    needs_recreate=true
  fi
  if $needs_recreate; then
    echo "[setup] removing incompatible venv (found $VENV_MM or 3.13 artifacts)"
    rm -rf "$VENV"
  fi
fi

if [ ! -d "$VENV" ]; then
  echo "[setup] creating venv: $PY -m venv $VENV"
  "$PY" -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

# Re-check active interpreter version and pip linkage
ACTIVE_MM="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PIP_WHICH="$(command -v pip || true)"
PIP_INFO="$(python -c 'import sys,sysconfig; print(sys.executable); print(sys.version); print(sysconfig.get_paths()["purelib"])')"
echo "[setup] active venv Python: $ACTIVE_MM"
echo "[setup] pip: $PIP_WHICH"
echo "[setup] site-packages: $(echo "$PIP_INFO" | tail -n1)"

if [ -d "$VENV/lib/python3.13" ]; then
  echo "[setup] ERROR: venv still contains python3.13 artifacts. Please remove .venv manually and rerun." >&2
  exit 1
fi

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