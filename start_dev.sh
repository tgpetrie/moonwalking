#!/usr/bin/env bash
# start_dev.sh
# Starts backend in the current terminal and opens the frontend dev server
# in a new terminal window so both outputs are visible and can be quit separately.

set -euo pipefail

# Resolve repo root (script directory)
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

print() { echo "[start_dev] $*"; }

# Parse args
EXTERNAL=false
CLEANUP=false
FORCE=false
while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --external) EXTERNAL=true; shift ;;
    --cleanup) CLEANUP=true; shift ;;
    --force) FORCE=true; shift ;;
    -h|--help)
      echo "Usage: $0 [--external] [--cleanup] [--force]"
      echo "  --external   Open the frontend in an external Terminal.app/iTerm window instead of inside VS Code"
      echo "  --cleanup    Scan common dev ports and optionally kill processes listening there"
      echo "  --force      When used with --cleanup, kill without prompting"
      exit 0
      ;;
    *) shift ;;
  esac
done

# Activate virtualenv if present
if [ -d "$ROOT_DIR/.venv" ]; then
  print "Activating Python virtualenv"
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.venv/bin/activate"
fi

## Open frontend visibly. Priority order:
## If --external was passed -> Terminal.app / iTerm
## Else if running inside VS Code -> prefer tmux session (keeps things in integrated terminal)
## Else on macOS try Terminal.app / iTerm, else tmux, else print manual instruction
opened=false

if [ "$EXTERNAL" = true ]; then
  print "Force external terminal requested (--external)."
  if [[ "$(uname)" == "Darwin" ]]; then
    print "Attempting to open frontend in Terminal.app (external)..."
    if osascript -e "tell application \"Terminal\" to do script \"cd '$ROOT_DIR/frontend' && npm run dev\"" >/dev/null 2>&1; then
      print "Frontend opened in Terminal.app"
      opened=true
    else
      print "Terminal.app launch failed, trying iTerm..."
      if osascript -e "tell application \"iTerm\" to create window with default profile command \"cd '$ROOT_DIR/frontend' && npm run dev\"" >/dev/null 2>&1; then
        print "Frontend opened in iTerm2"
        opened=true
      fi
    fi
  else
    print "--external is only implemented for macOS Terminal/iTerm. Please open a new terminal and run:"
    print "  cd '$ROOT_DIR/frontend' && npm run dev"
    opened=true
  fi
else
  # Prefer keeping panes inside VS Code integrated terminal if detected
  if [ -n "${VSCODE_PID-}" ] || [ "${TERM_PROGRAM-}" = "vscode" ]; then
    print "Detected VS Code integrated terminal. Using tmux to keep both processes inside VS Code."
    if command -v tmux >/dev/null 2>&1; then
      if ! tmux has-session -t devsession 2>/dev/null; then
        tmux new-session -d -s devsession -n backend
      fi
      # Remove old frontend window if present
      tmux list-windows -t devsession 2>/dev/null | grep -q frontend && tmux kill-window -t devsession:frontend 2>/dev/null || true
      tmux send-keys -t devsession:0 "clear; cd '$ROOT_DIR/backend'; exec python3 app.py" C-m
      tmux new-window -t devsession -n frontend "cd '$ROOT_DIR/frontend' && npm run dev"
      tmux select-window -t devsession:0 >/dev/null 2>&1 || true
      print "Launching tmux session 'devsession' inside this terminal. Attach to it to view both windows."
      tmux attach -t devsession
      exit 0
    else
      print "tmux not found. Falling back to external Terminal.app on macOS or manual instructions."
    fi
  fi

  # If not in VS Code or tmux not available, try macOS Terminal.app/iTerm
  if [[ "$(uname)" == "Darwin" ]]; then
    print "Attempting to open frontend in Terminal.app..."
    if osascript -e "tell application \"Terminal\" to do script \"cd '$ROOT_DIR/frontend' && npm run dev\"" >/dev/null 2>&1; then
      print "Frontend opened in Terminal.app"
      opened=true
    else
      print "Terminal.app launch failed, trying iTerm..."
      if osascript -e "tell application \"iTerm\" to create window with default profile command \"cd '$ROOT_DIR/frontend' && npm run dev\"" >/dev/null 2>&1; then
        print "Frontend opened in iTerm2"
        opened=true
      fi
    fi
  fi
fi

# Final fallback: tmux or manual instruction
if [ "$opened" = false ]; then
  if command -v tmux >/dev/null 2>&1; then
    print "Opening frontend in a new tmux window (tmux detected)..."
    if ! tmux has-session -t devsession 2>/dev/null; then
      tmux new-session -d -s devsession
    fi
    tmux new-window -t devsession -n frontend "cd '$ROOT_DIR/frontend' && npm run dev"
    print "Frontend started in tmux. Attach with: tmux attach -t devsession"
    opened=true
  else
    print "No Terminal automation available. Please open a new terminal and run:"
    print "  cd '$ROOT_DIR/frontend' && npm run dev"
  fi
fi

# --- port cleanup utilities ---
PORTS=(5173 5174 5175 5176 5177 5178 5179 5180 5000 5001)

scan_ports() {
  local found=0
  local port pid cmd
  printf "Checking ports: %s\n" "${PORTS[*]}"
  for port in "${PORTS[@]}"; do
    # lsof -t returns PIDs listening on the port
    pids=$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
      for pid in $pids; do
        cmd=$(ps -p "$pid" -o pid= -o command= 2>/dev/null || true)
        printf "  Port %s -> PID %s -> %s\n" "$port" "$pid" "${cmd//\n/ }"
        found=1
      done
    fi
  done
  return $found
}

kill_found_pids() {
  local pids_list=
  for port in "${PORTS[@]}"; do
    pids=$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
      for pid in $pids; do
        pids_list+="$pid "
      done
    fi
  done
  if [ -z "$pids_list" ]; then
    echo "No dev server processes found to kill."
    return 0
  fi
  echo "Killing PIDs: $pids_list"
  # try graceful first
  kill $pids_list 2>/dev/null || true
  sleep 1
  # force kill remaining
  for pid in $pids_list; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  echo "Kill sequence complete."
}

# If requested, scan and optionally kill processes on common dev ports
if [ "$CLEANUP" = true ]; then
  if scan_ports; then
    if [ "$FORCE" = true ]; then
      echo "--force provided: killing found dev processes without prompt."
      kill_found_pids
    else
      echo "Found processes listening on common dev ports above. Kill them? [y/N]"
      read -r resp
      if [[ "$resp" =~ ^[Yy]$ ]]; then
        kill_found_pids
      else
        echo "Skipping kill. Continuing startup."
      fi
    fi
  else
    echo "No dev server processes detected on common ports."
  fi
fi

# Run backend in the current terminal (foreground)
print "Starting backend in this terminal: $ROOT_DIR/backend -> python3 app.py"
cd "$ROOT_DIR/backend"
exec python3 app.py
