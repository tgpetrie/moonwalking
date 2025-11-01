# Routes (Base http://127.0.0.1:5001)
GET /api/health → { "ok": true }
GET /api/component/gainers-table-1min → { "data": [Gainers1mRow...] }
GET /api/component/gainers-table      → { "data": [Gainers3mRow...] }
GET /api/component/losers-table       → { "data": [Losers3mRow...] }
GET /api/component/top-movers-bar     → { "data": [Banner1hItem...] }
GET /api/component/banner-volume-1h   → { "data": [Volume1hItem...] }
POST /api/ask/log { "q": "str", "ctx": {...} } → { "ok": true, "logged_total": n }
GET  /api/ask/metrics → { "logged_total": n }
POST /api/learn/complete { "delta": 1 } → { "completed": n, "streak": s, "last_ts": t }
GET  /api/learn/state → { "completed": n, "streak": s, "last_ts": t }
GET  /api/sentiment/history → { "items": [SentimentSnapshot...] }
POST /api/sentiment/batch { "symbols": [...], "ttl_seconds": 30 } → { "items": [SentimentBatchItem...] }
