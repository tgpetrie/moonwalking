#!/usr/bin/env zsh
set -euo pipefail

cd /Users/cdmxx/Documents/moonwalkings/frontend || { echo "bad CWD"; exit 1; }

echo "— kill any Vite on 5173/5174 —"
lsof -t -iTCP:5173 -sTCP:LISTEN 2>/dev/null | xargs -I{} kill -9 {} 2>/dev/null || true
nlsof -t -iTCP:5174 -sTCP:LISTEN 2>/dev/null | xargs -I{} kill -9 {} 2>/dev/null || true
pkill -f "[n]px vite" 2>/dev/null || true
pkill -f "node .*vite.*127\.0\.0\.1" 2>/dev/null || true
sleep 0.4

echo "— clear caches/logs —"
rm -rf node_modules/.vite .vite ../vite_dev.log ../vite.pid vite_dev.log vite.pid 2>/dev/null || true

echo "— sanity: only one vite config & one entry html —"
rm -f tmp_vite_index.html vite.config.js 2>/dev/null || true
if [ ! -f vite.config.ts ]; then
  cat > vite.config.ts <<'TS'
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5174, strictPort: true, proxy: {} },
});
TS
fi
grep -q '/src/main.jsx' index.html || sed -i '' 's#</head>#<script type="module" src="/src/main.jsx"></script>\n</head>#' index.html

echo "— minimal probe file —"
cat > probe.html <<'HTML'
<!doctype html><meta charset="utf-8"><title>probe</title>
<body style="background:#111;color:#ddd;font-family:system-ui"><h1>probe ok</h1></body>
HTML

echo "— start Vite in background with hard logs —"
env NODE_OPTIONS='--trace-warnings' nohup npx vite --host 127.0.0.1 --port 5174 --debug > ../vite_dev.log 2>&1 &
echo $! > ../vite.pid
sleep 1

echo "— verify listener —"
if ! lsof -nP -iTCP:5174 -sTCP:LISTEN; then
  echo "Vite failed to bind 5174"; sed -n '1,160p' ../vite_dev.log; exit 1
fi

echo "— log tail —"
tail -n 40 ../vite_dev.log || true

echo "— smoke: index.html —"
curl -sS --http1.0 -D - http://127.0.0.1:5174/index.html -o /tmp/index.html | sed -n '1,20p'
head -n 12 /tmp/index.html || true

echo "— smoke: main.jsx —"
curl -sS --max-time 5 http://127.0.0.1:5174/src/main.jsx | sed -n '1,40p' || echo "no main.jsx bytes"

echo "— smoke: vite runtime —"
curl -sS --max-time 5 http://127.0.0.1:5174/@vite/client | sed -n '1,20p' || echo "no @vite/client bytes"

echo "— smoke: static probe (bypasses your imports) —"
curl -sS --max-time 5 http://127.0.0.1:5174/probe.html | sed -n '1,10p' || echo "no probe bytes"

echo "DONE"
