#!/usr/bin/env bash
set -euo pipefail

# kill-repo-ports.sh
# Safely stop dev servers tied to the current repo (macOS/Linux).
#
# What it kills (listeners only):
#   1) Processes whose CWD is inside this repo, OR
#   2) Processes whose command line mentions this repo path, OR
#   3) Processes on common dev ports AND whose command looks like a dev tool
#
# Default behavior:
#   - Shows what it will kill
#   - Prompts before killing (use --yes to skip prompt)
#   - Sends SIGTERM first, then SIGKILL if still listening (use --hard to go straight to SIGKILL)
#
# Usage:
#   ./kill-repo-ports.sh
#   ./kill-repo-ports.sh --dry-run
#   ./kill-repo-ports.sh --yes
#   ./kill-repo-ports.sh --yes --hard
#   ./kill-repo-ports.sh --ports 5003,5174,8787

DRY_RUN=0
ASSUME_YES=0
HARD=0
PORTS_CSV=""
EXTRA_KEYWORDS=""

print_help() {
  cat <<'EOF'
kill-repo-ports.sh

Options:
  --dry-run            Print matches, do not kill
  --yes                Do not prompt
  --hard               Skip SIGTERM, go straight to SIGKILL
  --ports <csv>        Only consider these ports (e.g. 5003,5174,8787)
  --keywords <csv>     Extra keywords to match against process command (e.g. "cbmo4ers,moonwalkings")
  -h, --help           Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    --hard) HARD=1; shift ;;
    --ports) PORTS_CSV="${2:-}"; shift 2 ;;
    --keywords) EXTRA_KEYWORDS="${2:-}"; shift 2 ;;
    -h|--help) print_help; exit 0 ;;
    *) echo "Unknown arg: $1"; print_help; exit 2 ;;
  esac
done

if ! command -v lsof >/dev/null 2>&1; then
  echo "Error: lsof not found. Install it (macOS usually has it)."
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
REPO_ROOT="${REPO_ROOT%/}"

BASE_KEYWORDS=(
  "node" "npm" "pnpm" "yarn" "vite" "webpack" "next" "react-scripts"
  "python" "python3" "flask" "gunicorn" "uvicorn" "hypercorn"
  "wrangler" "cloudflared" "vercel" "netlify" "ngrok"
)

IFS=',' read -r -a EXTRA_KW_ARR <<< "${EXTRA_KEYWORDS:-}"
KEYWORDS=("${BASE_KEYWORDS[@]}")
for k in "${EXTRA_KW_ARR[@]}"; do
  [[ -n "${k// /}" ]] && KEYWORDS+=("$k")
done

DEFAULT_PORTS=()
for p in $(seq 5000 5010); do DEFAULT_PORTS+=("$p"); done
for p in $(seq 5170 5190); do DEFAULT_PORTS+=("$p"); done
for p in $(seq 8000 8010); do DEFAULT_PORTS+=("$p"); done
for p in 8787 8788 8790; do DEFAULT_PORTS+=("$p"); done

PORTS=()
if [[ -n "$PORTS_CSV" ]]; then
  IFS=',' read -r -a PORTS <<< "$PORTS_CSV"
else
  PORTS=("${DEFAULT_PORTS[@]}")
fi

contains_repo_in_cmd() {
  local pid="$1"
  local cmd
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  [[ -n "$cmd" ]] && [[ "$cmd" == *"$REPO_ROOT"* ]]
}

cwd_in_repo() {
  local pid="$1"
  local cwd
  cwd="$(lsof -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1 || true)"
  [[ -n "$cwd" ]] && [[ "$cwd" == "$REPO_ROOT"* ]]
}

cmd_matches_keywords() {
  local pid="$1"
  local cmd
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  [[ -z "$cmd" ]] && return 1
  for kw in "${KEYWORDS[@]}"; do
    [[ -n "$kw" ]] && [[ "$cmd" == *"$kw"* ]] && return 0
  done
  return 1
}

declare -A CANDIDATES
for port in "${PORTS[@]}"; do
  [[ -z "${port// /}" ]] && continue
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    CANDIDATES["$pid"]+="${port}/tcp "
  done < <(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true)

  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    CANDIDATES["$pid"]+="${port}/udp "
  done < <(lsof -nP -iUDP:"$port" -t 2>/dev/null | sort -u || true)
done

while IFS= read -r pid; do
  [[ -z "$pid" ]] && continue
  if cwd_in_repo "$pid" || contains_repo_in_cmd "$pid"; then
    CANDIDATES["$pid"]+="(repo-scan) "
  fi
done < <(lsof -nP -iTCP -sTCP:LISTEN -t 2>/dev/null | sort -u || true)

declare -A TO_KILL
for pid in "${!CANDIDATES[@]}"; do
  if cwd_in_repo "$pid" || contains_repo_in_cmd "$pid"; then
    TO_KILL["$pid"]=1
    continue
  fi

  if cmd_matches_keywords "$pid"; then
    TO_KILL["$pid"]=1
  fi
done

if [[ ${#TO_KILL[@]} -eq 0 ]]; then
  echo "No repo/dev-scoped listeners found."
  echo "Repo: $REPO_ROOT"
  exit 0
fi

echo "Repo: $REPO_ROOT"
echo "Matched listener processes:"
for pid in "${!TO_KILL[@]}"; do
  ports="${CANDIDATES[$pid]}"
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  echo "  PID $pid  ports: ${ports:-unknown}  cmd: $cmd"
done | sort -V

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run: no processes killed."
  exit 0
fi

if [[ "$ASSUME_YES" -ne 1 ]]; then
  echo
  read -r -p "Kill these processes? [y/N] " ans
  case "${ans:-}" in
    y|Y|yes|YES) ;;
    *) echo "Aborted."; exit 0 ;;
  esac
fi

pids=("${!TO_KILL[@]}")

if [[ "$HARD" -eq 1 ]]; then
  echo "Sending SIGKILL to: ${pids[*]}"
  kill -9 "${pids[@]}" 2>/dev/null || true
else
  echo "Sending SIGTERM to: ${pids[*]}"
  kill "${pids[@]}" 2>/dev/null || true
  sleep 0.6
  still=()
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then still+=("$pid"); fi
  done
  if [[ ${#still[@]} -gt 0 ]]; then
    echo "Escalating to SIGKILL for: ${still[*]}"
    kill -9 "${still[@]}" 2>/dev/null || true
  fi
fi

echo "Done. You can verify with:"
echo "  lsof -nP -iTCP -sTCP:LISTEN | head"
