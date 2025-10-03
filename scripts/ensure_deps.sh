#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log() {
  printf '[deps] %s\n' "$1"
}

hash_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$file" | awk '{print $1}'
  else
    local py=""
    for candidate in python3 python; do
      if command -v "$candidate" >/dev/null 2>&1; then
        py="$candidate"
        break
      fi
    done
    if [ -z "$py" ]; then
      log "no hashing utility available" >&2
      return 1
    fi
    "$py" - <<'PY' "$file"
import hashlib, pathlib, sys
path = pathlib.Path(sys.argv[1])
data = path.read_bytes()
print(hashlib.sha256(data).hexdigest())
PY
  fi
}

ensure_python_env() {
  local venv=".venv"
  local python_bin=""
  local setup_ran=false

  if [ ! -x "$venv/bin/python" ]; then
    if [ -x "$ROOT_DIR/setup_dev.sh" ]; then
      log "virtualenv missing; running setup_dev.sh"
      "$ROOT_DIR/setup_dev.sh"
      setup_ran=true
    fi
  fi

  if [ -x "$venv/bin/python" ]; then
    python_bin="$venv/bin/python"
  else
    for candidate in python3.12 python3.11 python3 python; do
      if command -v "$candidate" >/dev/null 2>&1; then
        python_bin="$candidate"
        break
      fi
    done
    if [ -z "$python_bin" ]; then
      log "python not found; install Python 3.12+ and re-run"
      return 1
    fi
    log "creating virtualenv via $python_bin"
    "$python_bin" -m venv "$venv"
    python_bin="$venv/bin/python"
  fi

  local py_mm
  py_mm=$("$python_bin" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  if [ "${py_mm%%.*}" = "3" ] && [ "${py_mm##*.}" -gt 12 ]; then
    if [ -x "$ROOT_DIR/setup_dev.sh" ]; then
      log "venv uses Python ${py_mm}; running setup_dev.sh for compatibility"
      "$ROOT_DIR/setup_dev.sh"
      setup_ran=true
      python_bin="$venv/bin/python"
    else
      log "Python ${py_mm} detected; install Python 3.12 and rerun" >&2
      return 1
    fi
  fi

  if [ -d "$venv/lib/python3.13" ] || [ -x "$venv/bin/python3.13" ] || { [ -f "$venv/bin/pip" ] && grep -q 'python3.13' "$venv/bin/pip"; }; then
    if [ -x "$ROOT_DIR/setup_dev.sh" ]; then
      log "detected Python 3.13 artifacts; running setup_dev.sh"
      "$ROOT_DIR/setup_dev.sh"
      setup_ran=true
      python_bin="$venv/bin/python"
    else
      log "Python 3.13 artifacts detected; remove .venv manually and rerun" >&2
      return 1
    fi
  fi

  local pip_bin="$venv/bin/pip"
  if [ ! -x "$pip_bin" ]; then
    "$python_bin" -m ensurepip
    pip_bin="$venv/bin/pip"
  fi

  if [ "$setup_ran" = true ]; then
    touch "$venv/.pip-upgraded"
  elif [ ! -f "$venv/.pip-upgraded" ]; then
    log "upgrading pip inside venv"
    "$pip_bin" install --upgrade pip setuptools wheel >/dev/null
    touch "$venv/.pip-upgraded"
  fi

  local req_file="backend/requirements.txt"
  if [ -f "$req_file" ]; then
    local req_hash
    req_hash=$(hash_file "$req_file")
    local lock_file="$venv/.requirements.hash"
    local current_hash=""
    if [ -f "$lock_file" ]; then
      current_hash=$(cat "$lock_file")
    fi
    if [ "$setup_ran" = true ]; then
      current_hash="$req_hash"
      echo "$req_hash" > "$lock_file"
    fi
    if [ "$req_hash" != "$current_hash" ]; then
      log "installing backend requirements"
      "$pip_bin" install -r "$req_file"
      echo "$req_hash" > "$lock_file"
    else
      log "backend requirements unchanged"
    fi
  fi
}

ensure_node_modules() {
  local frontend_dir="frontend"
  if [ ! -d "$frontend_dir" ] || [ ! -f "$frontend_dir/package.json" ]; then
    return 0
  fi

  pushd "$frontend_dir" >/dev/null
  local hash_source=""
  if [ -f package-lock.json ]; then
    hash_source="package-lock.json"
  else
    hash_source="package.json"
  fi
  local deps_hash
  deps_hash=$(hash_file "$hash_source")
  local stamp="node_modules/.deps.hash"
  local current_hash=""
  if [ -f "$stamp" ]; then
    current_hash=$(cat "$stamp")
  fi
  if [ ! -d node_modules ] || [ "$deps_hash" != "$current_hash" ]; then
    log "installing frontend dependencies"
    npm install --no-fund --no-audit
    mkdir -p node_modules
    echo "$deps_hash" > "$stamp"
  else
    log "frontend dependencies unchanged"
  fi
  popd >/dev/null
}

ensure_python_env
ensure_node_modules
