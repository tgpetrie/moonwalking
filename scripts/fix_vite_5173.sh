#!/usr/bin/env bash
set -euo pipefail

APP="${APP:-$HOME/Documents/moonwalkings}"
FRONTEND="$APP/frontend"
LOG="/tmp/vite_run.log"
HOST="127.0.0.1"
PREF_PORT="${PORT:-5173}"

say() { printf "\n▶ %s\n" "$*"; }
die() { printf "\n✖ %s\n" "$*" >&2; exit 1; }

[[ -d "$FRONTEND" ]] || die "Frontend dir not found: $FRONTEND"
cd "$APP"

# 0) Who owns 5173?
say "Checking ownership of :$PREF_PORT…"
PID="$(lsof -nP -iTCP:$PREF_PORT -sTCP:LISTEN -t 2>/dev/null || true)"
if [[ -n "$PID" ]]; then
  CMD="$(ps -o command= -p "$PID" 2>/dev/null || true)"
  say "PID on $PREF_PORT: $PID"
  echo "command: $CMD"
  if ! echo "$CMD" | grep -qi "vite"; then
    say "Not Vite. Killing $PID."
    kill -9 "$PID" 2>/dev/null || true
  else
    say "It's Vite. Leaving it."
  fi
else
  say "No process listening on $PREF_PORT."
fi

# 1) index.html health + restore if empty/tiny
cd "$FRONTEND"
say "Verifying frontend/index.html…"
if [[ ! -f index.html ]]; then
  say "index.html missing — creating minimal file."
  touch index.html
fi

SZ="$(wc -c < index.html 2>/dev/null || echo 0)"
if [[ "$SZ" -lt 120 ]]; then
  cp index.html "index.html.bak.$(date +%s)" 2>/dev/null || true
  cat > index.html <<'HTML'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>BHABIT • Dev</title>
    <script type="module" src="/@vite/client"></script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
HTML
  say "Restored minimal index.html"
fi

# 2) Ensure main.jsx mounts #root and pulls CSS
say "Checking src/main.jsx and src/index.css wiring…"
mkdir -p src
if [[ ! -f src/main.jsx ]]; then
  cat > src/main.jsx <<'JSX'
import React from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(<App />)
JSX
  say "Created src/main.jsx (minimal)."
fi

if [[ ! -f src/App.jsx ]]; then
  cat > src/App.jsx <<'JSX'
export default function App() {
  return (
    <div style={{padding:'2rem'}}>
      <h1>BHABIT Dev</h1>
      <p>If you can read this, Vite + React is alive.</p>
    </div>
  )
}
JSX
  say "Created src/App.jsx (placeholder)."
fi

if [[ ! -f src/index.css ]]; then
  cat > src/index.css <<'CSS'
:root { --bg:#0b0b0f; --fg:#eaeaf0; }
html,body,#root { height:100%; }
body { margin:0; background:var(--bg); color:var(--fg); font-family: -apple-system, BlinkMacSystemFont, 'Raleway', sans-serif; }
CSS
  say "Created src/index.css."
fi

# 3) Ensure deps exist
say "Ensuring node_modules and vite deps exist…"
if [[ ! -d node_modules ]]; then
  npm install --silent
fi
npm pkg get devDependencies.vite >/dev/null 2>&1 || npm i -D vite --silent
npm pkg get dependencies.react >/dev/null 2>&1 || npm i react react-dom --silent

# 4) Pick a free port starting at 5173
pick_port() {
  local p="$1"
  for try in {0..10}; do
    local test=$((p+try))
    if ! lsof -nP -iTCP:$test -sTCP:LISTEN >/dev/null 2>&1; then
      echo "$test"; return 0
    fi
  done
  return 1
}
PORT="$(pick_port "$PREF_PORT")" || die "No free port found near $PREF_PORT"

# 5) Kill stray vite; start clean
say "Starting Vite on $HOST:$PORT…"
pkill -f "vite.*$HOST.*$PORT" 2>/dev/null || true
pkill -f vite 2>/dev/null || true
rm -f "$LOG"
# Prefer package script if present
if npm run | grep -qE '(^|\s)dev\s'; then
  (nohup npm run dev -- --host "$HOST" --port "$PORT" >"$LOG" 2>&1 &)
else
  (nohup npx vite --host "$HOST" --port "$PORT" >"$LOG" 2>&1 &)
fi
sleep 1

say "Vite PID(s):"
pgrep -fl "vite" || true

# 6) Probes
say "Probing / …"
curl -sSf -i "http://$HOST:$PORT/" | sed -n '1,60p' || true
say "Probing /@vite/client …"
curl -sSf -i "http://$HOST:$PORT/@vite/client" | sed -n '1,30p' || true
say "Probing /src/index.css (HEAD)…"
curl -sSI "http://$HOST:$PORT/src/index.css" | sed -n '1,20p' || true

say "Tail of $LOG:"
tail -n 200 "$LOG" || true

say "If you want, opening in default browser…"
if command -v open >/dev/null 2>&1; then open "http://$HOST:$PORT/"; fi

say "Done."
