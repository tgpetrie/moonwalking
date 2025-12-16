#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT}" ]]; then
  echo "Not inside a git repo."
  exit 1
fi

cd "$ROOT"

usage() {
  cat <<'USAGE'
moon_doctor.sh commands:

  where                 Show repo root, current dir, branch, and worktrees
  ports [port...]       Show listeners on ports (default: 5002 5173 5174)
  killports [port...]   Kill listeners on ports (default: 5002 5173 5174)
  probe [base]          Probe common endpoints on base (default: http://127.0.0.1:5002)
  promote <branch>      If HEAD is detached, create/switch to <branch> here
  snapshot "<msg>"      Commit all current changes with message (safe snapshot)

Examples:
  ./scripts/moon_doctor.sh where
  ./scripts/moon_doctor.sh ports
  ./scripts/moon_doctor.sh killports 5002
  ./scripts/moon_doctor.sh probe http://127.0.0.1:5002
  ./scripts/moon_doctor.sh promote fix/api-routes
  ./scripts/moon_doctor.sh snapshot "wip: stabilize api + ui"
USAGE
}

cmd="${1:-}"
shift || true

git_branch() {
  git symbolic-ref --short -q HEAD 2>/dev/null || echo "DETACHED"
}

do_where() {
  echo "Repo root: $ROOT"
  echo "CWD:      $(pwd)"
  echo "Branch:   $(git_branch)"
  echo
  echo "Worktrees:"
  git worktree list || true
}

do_ports() {
  local ports=("$@")
  if [[ ${#ports[@]} -eq 0 ]]; then ports=(5002 5173 5174); fi
  for p in "${ports[@]}"; do
    echo "Port $p:"
    lsof -nP -iTCP:"$p" -sTCP:LISTEN || true
    echo
  done
}

do_killports() {
  local ports=("$@")
  if [[ ${#ports[@]} -eq 0 ]]; then ports=(5002 5173 5174); fi
  for p in "${ports[@]}"; do
    local pids
    pids="$(lsof -tiTCP:"$p" -sTCP:LISTEN -n -P || true)"
    if [[ -n "${pids}" ]]; then
      echo "Killing port $p pids: ${pids}"
      kill -TERM ${pids} || true
      sleep 1
      kill -KILL ${pids} || true
    else
      echo "Port $p: no listeners"
    fi
  done
}

do_probe() {
  local base="${1:-http://127.0.0.1:5002}"
  echo "Probing base: $base"
  for path in /api/health /api/data /health /data /api/routes /routes; do
    code="$(curl -sS -o /dev/null -w "%{http_code}" "${base}${path}" || true)"
    echo "${code}  ${path}"
  done
}

do_promote() {
  local br="${1:-}"
  if [[ -z "$br" ]]; then echo "promote requires a branch name"; exit 2; fi
  if [[ "$(git_branch)" == "DETACHED" ]]; then
    echo "Detached HEAD -> creating branch $br"
    git switch -c "$br"
  else
    echo "Already on branch $(git_branch). Switching to $br (create if missing)."
    git switch "$br" 2>/dev/null || git switch -c "$br"
  fi
}

do_snapshot() {
  local msg="${1:-}"
  if [[ -z "$msg" ]]; then echo "snapshot requires a commit message"; exit 2; fi
  git add -A
  git commit -m "$msg" || {
    echo "Nothing to commit (or commit failed)."
    exit 0
  }
  echo "Committed: $msg"
}

case "$cmd" in
  where)      do_where ;;
  ports)      do_ports "$@" ;;
  killports)  do_killports "$@" ;;
  probe)      do_probe "$@" ;;
  promote)    do_promote "$@" ;;
  snapshot)   do_snapshot "$@" ;;
  ""|help|-h|--help) usage ;;
  *) echo "Unknown command: $cmd"; usage; exit 2 ;;
esac
