# app.py
from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

# -------------------------
# Config & small utilities
# -------------------------

APP = Flask(__name__)
# Allow Vite (5173) and same-origin during dev. Adjust as needed.
CORS(APP, resources={r"/api/*": {"origins": [r"http://localhost:*", r"http://127.0.0.1:*"]}})

DEFAULT_BACKEND_PORT = int(os.getenv("PORT", "5001"))
FRONTEND_PORT_FILE = Path(os.getenv("FRONTEND_PORT_FILE", "frontend.port"))
DEFAULT_FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "5173"))


def read_frontend_port() -> int:
    """Read intended frontend port from file; fall back to env/default."""
    try:
        txt = FRONTEND_PORT_FILE.read_text().strip()
        if txt:
            return int(txt)
    except Exception:
        pass
    # fall back to env or default
    return DEFAULT_FRONTEND_PORT


# -------------------------
# Simple watchlist storage
# -------------------------
DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
WATCHLIST_FILE = DATA_DIR / "watchlist.json"

def _load_watchlist() -> list[str]:
    try:
        import json
        if WATCHLIST_FILE.exists():
            return list({s.upper() for s in json.loads(WATCHLIST_FILE.read_text() or "[]") if isinstance(s, str)})
    except Exception:
        pass
    return []

def _save_watchlist(symbols: list[str]) -> None:
    import json
    try:
        WATCHLIST_FILE.write_text(json.dumps(sorted(list({s.upper() for s in symbols}))), encoding="utf-8")
    except Exception:
        # Do not crash the server on IO errors; caller can surface errors if needed.
        pass

def _normalize_symbol(sym: str | None) -> str | None:
    if not sym:
        return None
    s = sym.strip().upper()
    # very basic sanity: only allow letters, digits, dot, dash, colon
    import re
    return s if re.fullmatch(r"[A-Z0-9.\-:]+", s) else None


def tcp_listening(port: int, host: str = "127.0.0.1", timeout_s: float = 0.8) -> bool:
    """Lightweight TCP readiness check."""
    s = socket.socket()
    s.settimeout(timeout_s)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def backend_port() -> int:
    try:
        return int(os.getenv("PORT", DEFAULT_BACKEND_PORT))
    except Exception:
        return DEFAULT_BACKEND_PORT


# --- BEGIN: Frontend port discovery + server-info route ---
import os as _os
from pathlib import Path as _Path
from flask import jsonify as _jsonify

DEFAULT_FRONTEND_PORT = 5173
FRONTEND_PORT_FILE = _Path(__file__).parent / "frontend.port"

def read_frontend_port() -> int:
    """Read intended FE port from file first; fall back to env or default."""
    try:
        if FRONTEND_PORT_FILE.exists():
            txt = FRONTEND_PORT_FILE.read_text().strip()
            if txt:
                return int(txt)
    except Exception:
        pass
    return int(_os.getenv("FRONTEND_PORT", DEFAULT_FRONTEND_PORT))

@APP.get("/api/server-info")
def server_info():
    be_port = int(_os.getenv("PORT", _os.getenv("BACKEND_PORT", 5001)))
    fe_port = read_frontend_port()
    return _jsonify({
        "backend": {"port": be_port, "url": f"http://127.0.0.1:{be_port}"},
        "frontend": {
            "port": fe_port,
            "url": f"http://localhost:{fe_port}",
            "port_file": str(FRONTEND_PORT_FILE),
        },
    })
# --- END: Frontend port discovery + server-info route ---


# -------------
# API routes
# -------------

# ---- Minimal endpoints used by the frontend ----

@APP.get("/api/alerts/recent")
def recent_alerts():
    """
    Stub endpoint to unblock the UI. Returns an empty list by default.
    Frontend calls this as a poll; replace with real data source when ready.
    """
    limit = request.args.get("limit", type=int) or 25
    # TODO: wire to real alerts store; for now, return up to `limit` latest items (none).
    return jsonify([])


# ---- Watchlist endpoints (file-backed; safe for dev) ----

@APP.get("/api/watchlist")
def get_watchlist():
    """Return the current watchlist as a sorted list of symbols."""
    return jsonify(_load_watchlist())

@APP.post("/api/watchlist")
def add_to_watchlist():
    """
    Body: { "symbol": "TSLA" }  or  { "symbols": ["TSLA","AAPL"] }
    Adds one or more symbols (case-insensitive). Returns the updated list.
    """
    data = request.get_json(silent=True) or {}
    symbols = _load_watchlist()
    added = []

    # Accept single 'symbol' or plural 'symbols'
    maybe_one = _normalize_symbol(data.get("symbol"))
    if maybe_one:
        added.append(maybe_one)
    for s in data.get("symbols", []) or []:
        norm = _normalize_symbol(s)
        if norm:
            added.append(norm)

    if added:
        symbols = sorted(list({*symbols, *added}))
        _save_watchlist(symbols)
    return jsonify(symbols)

@APP.delete("/api/watchlist/<symbol>")
def delete_symbol(symbol: str):
    """Remove a single symbol from the watchlist. Returns the updated list."""
    norm = _normalize_symbol(symbol)
    symbols = [s for s in _load_watchlist() if s != norm]
    _save_watchlist(symbols)
    return jsonify(symbols)

@APP.put("/api/watchlist")
def replace_watchlist():
    """
    Replace the entire watchlist.
    Body: { "symbols": ["AAPL","MSFT"] }
    """
    data = request.get_json(silent=True) or {}
    new_syms = []
    for s in data.get("symbols", []) or []:
        norm = _normalize_symbol(s)
        if norm:
            new_syms.append(norm)
    _save_watchlist(sorted(list({*new_syms})))
    return jsonify(_load_watchlist())


@APP.get("/api/health")
def health():
    """Basic health check for probes and debugging."""
    fe_port = read_frontend_port()
    return jsonify(
        ok=True,
        backend={"port": backend_port()},
        frontend={"port": fe_port, "listening": tcp_listening(fe_port)},
    )





# Example placeholder endpoint your frontend might call
@APP.get("/api/example")
def example():
    return jsonify(message="Hello from Flask", port=backend_port())


# -------------
# Entrypoint
# -------------
def _log_startup():
    be = backend_port()
    fe = read_frontend_port()
    print(
        f"[backend] listening on http://0.0.0.0:{be} | "
        f"frontend intended http://localhost:{fe} "
        f"(file: {FRONTEND_PORT_FILE.resolve() if FRONTEND_PORT_FILE.exists() else 'missing'})"
    )
    if not tcp_listening(fe):
        print(
            f"[backend] note: frontend on :{fe} not listening yet "
            f"(this is normal during cold start; the FE start script should wait until ready)"
        )


if __name__ == "__main__":
    # For local debug only. In prod/dev you likely use gunicorn:
    #   gunicorn app:app -b 0.0.0.0:$PORT
    _log_startup()
    APP.run(host="0.0.0.0", port=backend_port(), debug=True)