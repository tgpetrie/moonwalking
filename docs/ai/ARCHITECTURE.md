# Architecture
Frontend :5173 → Dashboard + banners/tables/watchlist/info; hybrid hook (poll/socket).
Bridge :5100 → emits `gainers1m/gainers3m/losers3m/banner1h/vol1h/heartbeat`.
Backend :5001 → Coinbase fetch → snapshots → 1m/3m/1h calcs; Ask, Learning, Sentiment; `/api/component/*`.
Flow: Coinbase → Backend cache → Bridge events+HTTP → Frontend hooks → UI.
