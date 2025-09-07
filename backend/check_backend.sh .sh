#!/bin/zsh
# Simple backend health + data check script

echo "=== Health ==="
curl -s http://127.0.0.1:5001/health | jq .

echo "\n=== Latest Prices ==="
curl -s http://127.0.0.1:5001/api/prices | jq .

echo "\n=== Price Fetcher Metrics ==="
curl -s http://127.0.0.1:5001/api/price_fetch/metrics | jq .