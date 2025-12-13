#!/usr/bin/env bash

# Simple, NON-fatal backend check for 5001 + /api/health + /api/data

cd "$(dirname "$0")/.." || exit 1

echo '--- listener on 5001 ---'
lsof -iTCP:5001 -sTCP:LISTEN -n 2>/dev/null || echo 'no listener on 5001'

echo
echo '--- /api/health ---'
if ! curl -sS -D - http://127.0.0.1:5001/api/health | sed -n '1,8p'; then
  echo 'health request failed'
fi

echo
echo '--- /api/data summary ---'
if ! curl -sS http://127.0.0.1:5001/api/data \
  | jq '{g1m: (.gainers_1m // [] | length),
         g3m: (.gainers_3m // [] | length),
         l3m: (.losers_3m  // [] | length)}'; then
  echo 'data request failed'
fi

echo
echo '--- first items (if any) ---'
for K in gainers_1m gainers_3m losers_3m; do
  echo
  echo "-- ${K}[0] --"
  if ! curl -sS http://127.0.0.1:5001/api/data \
    | jq ".${K} | .[0] // \"<no item>\""; then
    echo "request failed for ${K}"
  fi
done

echo
echo '--- backend logs ---'
if [ -f backend/server.stdout ]; then
  echo 'backend/server.stdout (last 40)'
  tail -n 40 backend/server.stdout
else
  echo 'no backend/server.stdout'
fi

if [ -f backend/gunicorn.stdout ]; then
  echo
  echo 'backend/gunicorn.stdout (last 40)'
  tail -n 40 backend/gunicorn.stdout
else
  echo 'no backend/gunicorn.stdout'
fi

exit 0
