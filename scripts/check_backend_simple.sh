#!/usr/bin/env bash

# Simple, NON-fatal backend check for :5003 + /api/health + /data

cd "$(dirname "$0")/.." || exit 1

echo '--- listener on 5003 ---'
lsof -iTCP:5003 -sTCP:LISTEN -n 2>/dev/null || echo 'no listener on 5003'

echo
echo '--- /api/health ---'
if ! curl -sS -D - http://127.0.0.1:5003/api/health | sed -n '1,8p'; then
  echo 'health request failed'
fi

echo
echo '--- /data summary ---'
if ! curl -sS http://127.0.0.1:5003/data \
  | jq '{g1m: (.gainers_1m // [] | length),
         g3m: (.gainers_3m // [] | length),
         l3m: (.losers_3m  // [] | length),
         bprice: (.banner_1h_price // [] | length),
         bvol: (.banner_1h_volume // [] | length)}'; then
  echo 'data request failed'
fi


echo
echo '--- first items (if any) ---'
for K in gainers_1m gainers_3m losers_3m banner_1h_price banner_1h_volume; do
  echo
  echo "-- ${K}[0] --"
  if ! curl -sS http://127.0.0.1:5003/data \
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
