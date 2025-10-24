#!/usr/bin/env bash
set -euo pipefail
DEFAULT_PORTS=("5001" "5002" "5003" "5173" "5174" "5175")
PORTS=("$@"); [[ ${#PORTS[@]} -eq 0 ]] && PORTS=("${DEFAULT_PORTS[@]}")
cmd(){ command -v "$1" >/dev/null 2>&1; }
die(){ echo "[-] $*" >&2; exit 1; }
ok(){ echo "[+] $*"; }
info(){ echo "[i]  $*"; }
cmd lsof || die "lsof not found. Install via: brew install lsof (macOS) or apt/yum."

kill_port(){ local port="$1"
  mapfile -t pids < <(lsof -ti tcp:"$port" || true)
  if [[ ${#pids[@]} -eq 0 ]]; then info "Port $port already free."; return 0; fi
  info "Port $port in use by PID(s): ${pids[*]} — sending SIGTERM…"
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  for _ in {1..10}; do sleep 0.15; lsof -ti tcp:"$port" >/dev/null || { ok "Port $port freed cleanly."; return 0; }; done
  info "Escalating to SIGKILL on port $port…"
  mapfile -t pids2 < <(lsof -ti tcp:"$port" || true)
  for pid in "${pids2[@]}"; do kill -9 "$pid" 2>/dev/null || true; done
  sleep 0.15
  lsof -ti tcp:"$port" >/dev/null && die "Port $port still occupied. Inspect: lsof -nP -iTCP:$port -sTCP:LISTEN" || ok "Port $port freed (SIGKILL)."
}
for p in "${PORTS[@]}"; do [[ "$p" =~ ^[0-9]+$ ]] || die "Invalid port: $p"; kill_port "$p"; done
ok "All requested ports are free: ${PORTS[*]}"
