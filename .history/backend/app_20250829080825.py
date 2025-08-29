# app.py
from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify
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

@APP.get("/api/health")
def health():
    """Basic health check for probes and debugging."""
    fe_port = read_frontend_port()
    return jsonify(
        ok=True,
        backend={"port": backend_port()},
        frontend={"port": fe_port, "listening": tcp_listening(fe_port)},
    )


@APP.get("/api/server-info")
def server_info_old():
    """Report the URLs the app believes in, and whether FE is really up."""
    be_port = backend_port()
    fe_port = read_frontend_port()

    info = {
        "backendUrl": f"http://localhost:{be_port}",
        "frontendUrl": f"http://localhost:{fe_port}",
        "frontend": {
            "portFromFile": fe_port if FRONTEND_PORT_FILE.exists() else None,
            "listening": tcp_listening(fe_port),
            "portFilePath": str(FRONTEND_PORT_FILE.resolve()),
        },
        "env": {
            "PORT": os.getenv("PORT"),
            "FRONTEND_PORT": os.getenv("FRONTEND_PORT"),
            "FRONTEND_PORT_FILE": os.getenv("FRONTEND_PORT_FILE"),
        },
    }
    return jsonify(info)


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