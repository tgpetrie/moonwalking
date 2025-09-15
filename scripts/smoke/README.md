
# Smoke-test scripts

Place the scripts in `scripts/smoke/` and run from the repo root.

Examples:

Price loop:
```bash
scripts/smoke/price-loop.sh "https://moonwalking-worker.tgpetrie.workers.dev/api/price?symbol=BTC" 15 2
```

WebSocket capture:
```bash
scripts/smoke/ws-capture.sh "wss://moonwalking-worker.tgpetrie.workers.dev/ws" 30
```

Watchlist flow:
```bash
scripts/smoke/watchlist.sh "https://moonwalking-worker.tgpetrie.workers.dev"
```

Artifacts are written under `dev-evidence/logs` and `dev-evidence/headers`.
