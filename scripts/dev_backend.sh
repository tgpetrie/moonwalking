#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

pick_python() {
  # Look for a real Python 3.12 interpreter (avoid pyenv shims that resolve to a
  # different global). Test candidates by running a tiny Python invocation and
  # checking major/minor.
  local candidates=(
    "python3.12" 
    "/opt/homebrew/bin/python3"   # Apple Silicon brew
    "/usr/local/bin/python3"      # Intel brew
    "/usr/bin/python3"            # macOS system
    "python3"
  )

  for p in "${candidates[@]}"; do
    if command -v "$p" >/dev/null 2>&1; then
      # Get major.minor; suppress output errors
      ver=$("$(command -v "$p")" -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2>/dev/null || true)
      if [[ "$ver" == "3.12" ]]; then
        # Prefer the resolved path rather than a shim name
        command -v "$p" && return
      fi
    fi
  done

  # Fallback: any python3 we can find
  command -v python3 >/dev/null 2>&1 && { command -v python3; return; }
  echo ""
}

PY_BIN="$(pick_python)"
if [[ -z "$PY_BIN" ]]; then
  echo "[-] No python3 found. If you use pyenv: pyenv install -s 3.12.6 && pyenv local 3.12.6" >&2
  exit 1
fi
echo "[i] Using base Python: $PY_BIN"

# (Re)create venv if missing or broken
if [[ ! -d "$ROOT/.venv" ]]; then
  "$PY_BIN" -m venv "$ROOT/.venv"
fi
# Detect stale/broken venvs where scripts point to an old interpreter (e.g. .venv312)
if [[ -f "$ROOT/.venv/bin/flask" ]]; then
  shebang_line=$(head -n1 "$ROOT/.venv/bin/flask" || true)
  interpreter_path="$(echo "$shebang_line" | sed -n 's/^#!//p' || true)"
  if [[ -n "$interpreter_path" && ! -x "$interpreter_path" ]]; then
    echo "[i] Detected stale venv interpreter ($interpreter_path); rebuilding .venv..."
    rm -rf "$ROOT/.venv"
    "$PY_BIN" -m venv "$ROOT/.venv"
  fi
fi

VENV_PY="$ROOT/.venv/bin/python3"
[[ -x "$VENV_PY" ]] || VENV_PY="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "[i] Detected broken .venv; rebuilding…"
  rm -rf "$ROOT/.venv"
  "$PY_BIN" -m venv "$ROOT/.venv"
  VENV_PY="$ROOT/.venv/bin/python3"
fi
echo "[i] Venv Python: $($VENV_PY -V 2>&1)"

# Minimal, deterministic deps sync
MARKER="$ROOT/.venv/.deps_installed"
if [[ ! -f "$MARKER" || "$ROOT/backend/requirements.txt" -nt "$MARKER" ]]; then
  "$VENV_PY" -m pip install -U pip setuptools wheel
  "$VENV_PY" -m pip install -r "$ROOT/backend/requirements.txt"
  touch "$MARKER"
fi

export USE_1MIN_SEED="${USE_1MIN_SEED:-1}"
export FLASK_APP=app.py
echo "[i] USE_1MIN_SEED=$USE_1MIN_SEED"

# Run flask from venv directly (no activate, no shims)
exec "$ROOT/.venv/bin/flask" run --host 127.0.0.1 --port 5001
