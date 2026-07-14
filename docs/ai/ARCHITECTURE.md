# AI Architecture Summary

The authoritative architecture is the repository-root `ARCHITECTURE.md`.

```text
Browser :5173
    |
    v
Flask board API :5003
    |-- Coinbase WebSocket plus bounded REST fallback
    |-- one price/snapshot worker
    |-- one volume worker
    |-- SQLite baselines, alerts, and watchlists
    |-- /data, /api/alerts, /api/insights, /api/coin-intel
    |
    +--> FastAPI sentiment :8003
         |-- Alternative.me
         +-- CoinGecko global
```

Production serves the built frontend from Flask on one origin and runs one Gunicorn worker behind Tailscale.
