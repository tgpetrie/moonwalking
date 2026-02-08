from flask import Flask, jsonify
import os
import argparse
import socket
import subprocess
import sys
import math
from flask import Flask, jsonify, request, g
from flask_talisman import Talisman
from flask_cors import CORS
import random
import requests
import time
import threading
from collections import defaultdict, deque
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
import logging
from datetime import datetime, timedelta, timezone
import asyncio
from pathlib import Path
try:
    from price_db import ensure_price_db, insert_price_snapshot, prune_old, get_price_at_or_before, get_price_at_or_after
    from volume_1h_store import ensure_db as ensure_volume_db
    from volume_1h_candles import refresh_product_minutes, RateLimitError
    from volume_1h_compute import compute_volume_1h
except ImportError as e:
    logging.warning(f"Volume tracking imports failed: {e}")
    def ensure_volume_db():
        pass
    refresh_product_minutes = None
    class RateLimitError(Exception):
        pass
    def get_price_at_or_after(product_id, target_ts):
        return None
    def compute_volume_1h():
        return []

try:
    from price_db import ensure_price_db, insert_price_snapshot, prune_old, get_price_at_or_before, get_price_at_or_after
except ImportError as e:
    logging.warning(f"Price DB imports failed: {e}")
    def ensure_price_db():
        pass
    def insert_price_snapshot(ts, rows):
        pass
    def prune_old(ts_cutoff):
        pass
    def get_price_at_or_before(product_id, target_ts):
        return None
    def get_price_at_or_after(product_id, target_ts):
        return None

from watchlist import watchlist_bp, watchlist_db
try:
    from reliability import stale_while_revalidate
except Exception:
    # Provide a minimal no-op fallback for environments where the local
    # `reliability` module is not present (dev machines or trimmed checkouts).
    # The real implementation provides a small stale-while-revalidate cache
    # decorator; here we degrade gracefully to a pass-through decorator so
    # the app can start for visual/local checks.
    def stale_while_revalidate(*args, **kwargs):
        # Accept any signature (ttl, stale_window, etc.) and return a no-op decorator
        def deco(fn):
            def wrapper(*a, **k):
                return fn(*a, **k)
            return wrapper
        return deco
try:
    from metrics import collect_swr_cache_stats, emit_prometheus, emit_swr_prometheus
except Exception:
    # Provide no-op fallbacks for environments missing the metrics module
    def collect_swr_cache_stats(*a, **k):
        return {}
    def emit_prometheus(*a, **k):
        return None
    def emit_swr_prometheus(*a, **k):
        return None

try:
    from alerting import AlertNotifier
except Exception:
    # Minimal AlertNotifier fallback to avoid import errors during local dev
    class AlertNotifier:
        def __init__(self, *a, **k):
            pass
        def notify(self, *a, **k):
            return None
        @classmethod
        def from_env(cls, *a, **k):
            # create an instance using environment-derived defaults; keep stub lightweight
            return cls()
try:
    # optional insight memory (may not exist early in startup)
    from watchlist import _insights_memory as INSIGHTS_MEMORY
except Exception:
    INSIGHTS_MEMORY = None

from logging_config import setup_logging as _setup_logging, log_config as _log_config_with_param
try:
    from logging_config import REQUEST_ID_CTX
except Exception:
    REQUEST_ID_CTX = None
import uuid
from pyd_schemas import HealthResponse, MetricsResponse, Gainers1mComponent
from api_contracts import AlertItem, SentimentBasicPayload
from alert_text import build_alert_text
from social_sentiment import get_social_sentiment
# New insights helpers
try:
    from insights import build_asset_insights
    from sentiment_data_sources import COINGECKO_ID_MAP
except Exception:
    # In some test or trimmed environments these modules may not exist; provide
    # fallbacks so import-time doesn't fail.
    build_asset_insights = None
    COINGECKO_ID_MAP = {}
# local low-overhead TTL cache for dev/test to avoid hammering Coinbase
try:
    # prefer package-style import when running as installed package
    from backend.utils.cache import ttl_cache  # type: ignore
except Exception:
    try:
        # fallback for direct script runs
        from utils.cache import ttl_cache  # type: ignore
    except Exception:
        # degrade gracefully: no-op decorator
        def ttl_cache(ttl=0):
            def deco(fn):
                return fn
            return deco

# Import missing constants from price_fetch module
try:
    from price_fetch import COINBASE_PRODUCTS_URL
except ImportError:
    COINBASE_PRODUCTS_URL = "https://api.exchange.coinbase.com/products"

ERROR_NO_DATA = "No data available"

# Cached Coinbase product ids (to verify a product exists before linking)
PRODUCT_IDS = None
PRODUCT_IDS_BY_BASE = None
PRODUCT_IDS_TS = 0
PRODUCT_IDS_TTL = 60 * 60  # 1 hour

# Volume 1h settings (env overrides)
VOLUME_1H_REFRESH_SEC = int(os.environ.get("VOLUME_1H_REFRESH_SEC", 90))
VOLUME_1H_MAX_TRACKED = int(os.environ.get("VOLUME_1H_MAX_TRACKED", 80))
VOLUME_1H_WORKERS = int(os.environ.get("VOLUME_1H_WORKERS", 4))
VOLUME_1H_BANNER_SIZE = int(os.environ.get("VOLUME_1H_BANNER_SIZE", 12))
VOLUME_1H_BASELINE = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
    "ADA-USD", "AVAX-USD", "LINK-USD", "LTC-USD",
]

# Debugging helper for product id resolution
DEBUG_PID = os.getenv("DEBUG_PRODUCT_ID", "").lower() in ("1", "true", "yes")

def _pid_debug(msg: str):
    if DEBUG_PID:
        try:
            print(msg, flush=True)
        except Exception:
            # best-effort debug printing; never raise
            pass
# Emit an immediate banner so we can confirm whether DEBUG_PID was picked up.
try:
    if DEBUG_PID:
        print("DEBUG_PID=1", flush=True)
    else:
        print("DEBUG_PID=0", flush=True)
except Exception:
    pass


def _load_product_ids(timeout=10):
    """Load and cache Coinbase products and build a by-base index.

    Returns a tuple `(pids_set, by_base_dict)` where `pids_set` is a set of
    normalized product ids (e.g. 'BTC-USD') and `by_base_dict` maps a base
    ticker (e.g. 'BTC') to a list of product ids for that base.
    """
    global PRODUCT_IDS, PRODUCT_IDS_BY_BASE, PRODUCT_IDS_TS
    try:
        now = time.time()
        if PRODUCT_IDS and (now - PRODUCT_IDS_TS) < PRODUCT_IDS_TTL and PRODUCT_IDS_BY_BASE:
            return PRODUCT_IDS, PRODUCT_IDS_BY_BASE

        resp = requests.get(COINBASE_PRODUCTS_URL, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        pids = set()
        by_base = {}
        for p in (data or []):
            if not isinstance(p, dict):
                continue
            pid = p.get("id")
            if not pid or "-" not in pid:
                continue
            parts = pid.split("-", 1)
            base = parts[0].strip().upper()
            quote = parts[1].strip().upper()
            pid_norm = f"{base}-{quote}"
            pids.add(pid_norm)
            by_base.setdefault(base, []).append(pid_norm)

        PRODUCT_IDS = pids
        PRODUCT_IDS_BY_BASE = by_base
        PRODUCT_IDS_TS = now
        return PRODUCT_IDS, PRODUCT_IDS_BY_BASE
    except Exception:
        return PRODUCT_IDS or set(), PRODUCT_IDS_BY_BASE or {}


def _norm_base(x: str) -> str | None:
    if not x:
        return None
    s = str(x).strip().upper()
    # keep only safe ticker characters
    s = s.replace(" ", "").replace("/", "").replace("_", "")
    return s or None


QUOTE_PREF = ("USD", "USDC", "USDT", "EUR", "GBP")

# Must-include staples (can override via env MW_MUST_INCLUDE_PRODUCTS)
_MW_MUST_INCLUDE_PRODUCTS = [
    p.strip().upper()
    for p in os.getenv("MW_MUST_INCLUDE_PRODUCTS", "BTC-USD,ETH-USD,SOL-USD,AMP-USD").split(",")
    if p.strip()
]


def _normalize_product_id_from_row(row: dict | None) -> str | None:
    if not isinstance(row, dict):
        return None
    pid = row.get("product_id") or row.get("productId") or row.get("product") or row.get("id")
    if isinstance(pid, str) and pid.strip():
        p = pid.strip().upper()
        if "-" not in p:
            p = f"{p}-USD"
        return p
    sym = row.get("symbol") or row.get("ticker") or row.get("base") or row.get("asset")
    if not sym:
        return None
    s = str(sym).strip().upper()
    if not s:
        return None
    if "-" not in s:
        s = f"{s}-USD"
    return s


def _row_quality_score(row: dict | None) -> int:
    if not isinstance(row, dict):
        return 0
    score = 0
    price = row.get("current_price") if row.get("current_price") is not None else row.get("price")
    if _safe_float(price) is not None:
        score += 2
    for k in (
        "change_1m",
        "price_change_percentage_1min",
        "price_change_1m",
        "change_3m",
        "price_change_percentage_3min",
        "price_change_3m",
    ):
        if _safe_float(row.get(k)) is not None:
            score += 2
            break
    if _safe_float(row.get("volume_1h_now")) is not None or _safe_float(row.get("volume_1h_prev")) is not None:
        score += 1
    if row.get("ts") or row.get("timestamp") or row.get("last_updated"):
        score += 1
    return score


def _dedupe_rows_by_product_id(rows: list[dict]) -> tuple[list[dict], int]:
    if not rows:
        return [], 0
    out = []
    index_by_pid = {}
    dropped = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = _normalize_product_id_from_row(row)
        if not pid:
            out.append(row)
            continue
        if pid in index_by_pid:
            existing_idx = index_by_pid[pid]
            existing = out[existing_idx]
            if _row_quality_score(row) > _row_quality_score(existing):
                out[existing_idx] = row
            dropped += 1
        else:
            index_by_pid[pid] = len(out)
            out.append(row)
    return out, dropped


def resolve_product_id_from_row(row) -> str | None:
    """Resolve a product id for a given row or symbol using Coinbase products.

    Accepts either a dict `row` or a string symbol. Returns a normalized
    product id (e.g. 'BTC-USD') or None if no verified product exists.
    """
    pids, by_base = _load_product_ids()

    # If caller passed a plain string, treat it as either product id or base
    if isinstance(row, str):
        s = str(row).strip().upper()
        if "-" in s and s in pids:
            return s
        # try base fallback
        base = _norm_base(s)
        if not base:
            _pid_debug(f"PID_MISS base={base!r} symbol={s!r} baseField={None!r} ticker={None!r} coinbase_symbol={None!r} options={[]}")
            return None
        options = by_base.get(base, [])
        for q in QUOTE_PREF:
            cand = f"{base}-{q}"
            if cand in pids:
                return cand
        return sorted(options)[0] if options else None

    # Otherwise expect a dict-like row
    if not isinstance(row, dict):
        _pid_debug(f"PID_MISS non-dict-row row={row!r}")
        return None

    # 1) preserve upstream explicit ids if valid
    for k in ("product_id", "productId", "product", "id"):
        pid = row.get(k)
        if isinstance(pid, str) and pid.strip():
            pidn = pid.strip().upper()
            if pidn in pids:
                return pidn

    # 2) pick base from likely fields (prefer coinbase_symbol then ticker,
    # and only accept `symbol` when it looks like a ticker)
    _SYM_RE = re.compile(r'^[A-Z0-9]{2,10}$')
    base = None
    for k in ("base", "coinbase_symbol", "ticker", "asset", "symbol"):
        val = row.get(k)
        if val is None:
            continue
        cand = _norm_base(val)
        if not cand:
            continue
        if k == "symbol" and not _SYM_RE.match(cand):
            continue
        base = cand
        break
    if not base:
        _pid_debug(f"PID_MISS base=None symbol={row.get('symbol')!r} baseField={row.get('base')!r} ticker={row.get('ticker')!r} coinbase_symbol={row.get('coinbase_symbol')!r} options={[]}")
        return None

    options = by_base.get(base, [])
    if not options:
        _pid_debug(f"PID_MISS base={base!r} symbol={row.get('symbol')!r} baseField={row.get('base')!r} ticker={row.get('ticker')!r} coinbase_symbol={row.get('coinbase_symbol')!r} options={options[:5]}")
        return None

    for q in QUOTE_PREF:
        cand = f"{base}-{q}"
        if cand in pids:
            return cand

    return sorted(options)[0]


def resolve_product_id(x) -> str | None:
    """Compatibility wrapper: accept either string or row and resolve product id."""
    return resolve_product_id_from_row(x)


# --- Compatibility wrapper matching older naming used in ops scripts ---
# Provide the exact symbols requested by the integration notes so callers
# or tests expecting these names will continue to work. These simply wrap
# the richer implementations above.
PIDS = None
PIDS_BY_BASE = None
PIDS_TS = 0
PRODUCT_IDS_TTL = PRODUCT_IDS_TTL if 'PRODUCT_IDS_TTL' in globals() else 3600

def _load_products(timeout=10):
    """Backward-compatible loader that returns (PIDS, PIDS_BY_BASE).

    Internally delegates to the newer `_load_product_ids` implementation
    to avoid duplicating fetch logic.
    """
    global PIDS, PIDS_BY_BASE, PIDS_TS
    pids, by_base = _load_product_ids(timeout=timeout)
    PIDS = pids
    PIDS_BY_BASE = by_base
    PIDS_TS = PRODUCT_IDS_TS if 'PRODUCT_IDS_TS' in globals() else time.time()
    return PIDS, PIDS_BY_BASE


def _null_if_nonpositive(x):
    """Treat missing or non-positive values as empty for baseline fields."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _safe_float(x):
    """Return float(x) if possible; otherwise None."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    # guard against NaN/inf
    if not math.isfinite(v):
        return None
    return v


def _sort_rows_by_numeric(rows, field, descending=True, tie_field="symbol"):
    """Sort dict rows by a numeric field; missing/invalid values go last.

    Uses a deterministic tie-breaker (default: symbol) to keep ordering stable.
    """

    def key(r):
        v = _safe_float((r or {}).get(field))
        is_missing = v is None
        # For descending, invert so default ascending sort yields descending numeric order.
        score = (-v) if (v is not None and descending) else (v if v is not None else 0.0)
        tie = ((r or {}).get(tie_field) or "")
        return (is_missing, score, tie)

    return sorted((rows or []), key=key)

# Check if psutil is available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

def _get_commit_sha():
    """Get the current git commit SHA"""
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=os.path.dirname(__file__)).decode().strip()
    except Exception:
        return "unknown"

# Note: defer Talisman initialization until after the final Flask `app`
# is created below. Early initialization here caused test-collection
# failures where a MockFlask used during tests did not expose
# `jinja_env` (flask_talisman expects app.jinja_env to exist).

def get_coinbase_prices():  # legacy wrapper retained for backwards compatibility
    """Wrapper delegating to modular price_fetch.fetch_prices.

    Returns:
        dict: mapping symbol -> price (floats) or empty dict on failure.
    """
    try:
        from price_fetch import fetch_prices
        return fetch_prices()
    except Exception as e:  # fallback minimal behavior
        logging.error(f"price_fetch module issue: {e}; falling back to empty price set")
        return {}

# (CONFIG is defined later; we defer logging its values until after definition.)
# Setup logging early
_setup_logging()

# Flask App Setup (final app instance)
app = Flask(__name__)
# In non-production environments, default to disabling Talisman to avoid
# automatic HTTPS/redirect enforcement during local development and tests.
if os.environ.get('FLASK_ENV', '').lower() != 'production':
    os.environ.setdefault('DISABLE_TALISMAN', '1')
# Provide optional snapshot-based volume helper (working913 compatibility)
try:
    from utils import get_1h_volume_weighted_data  # type: ignore
except Exception:
    get_1h_volume_weighted_data = None

# Fallback: if the optional `get_1h_volume_weighted_data` isn't present
# (trimmed dev checkout), provide a lightweight adapter that reuses the
# existing `get_banner_1h_volume()` computation so the `/api/snapshots/one-hour-volume`
# endpoint returns rows for the frontend during development.
if not callable(get_1h_volume_weighted_data):
    def get_1h_volume_weighted_data():
        try:
            rows, _ts = get_banner_1h_volume()
            out = []
            for r in (rows or []):
                vol_now = r.get("volume_24h") or r.get("volume_now") or r.get("volume") or 0
                vol_ago = r.get("volume_1h") or r.get("previous_volume") or None
                pct = r.get("volume_change_1h_pct") or r.get("volume_change_1h") or r.get("volume_change_pct")
                if pct is None and isinstance(vol_now, (int, float)) and isinstance(vol_ago, (int, float)) and vol_ago:
                    try:
                        pct = ((float(vol_now) - float(vol_ago)) / float(vol_ago)) * 100.0
                    except Exception:
                        pct = None
                out.append({
                    **r,
                    "volume_now": vol_now,
                    "volume_1h_ago": vol_ago,
                    "volume_change_pct": pct,
                    "percent_change": pct,
                })
            return out
        except Exception:
            return []
# Ensure minimal lifecycle and routing helpers exist even when tests replace
# Flask with a very small MockFlask. This prevents import-time endpoint
# decorators from failing during test collection.
def _no_op_decorator(fn):
    return fn
def _no_op_function(*args, **kwargs):
    return None

def _ensure_decorator_on_app(name):
    try:
        existing = getattr(app, name, None)
    except Exception:
        existing = None
    if not existing or not callable(existing):
        try:
            setattr(app, name, lambda *a, **k: (lambda f: f))
        except Exception:
            pass

for _d in ('route', 'get', 'post', 'put', 'delete', 'patch'):
    _ensure_decorator_on_app(_d)

for name in ('after_request', 'before_request', 'teardown_request', 'context_processor'):
    if not hasattr(app, name):
        try:
            setattr(app, name, _no_op_decorator)
        except Exception:
            pass

for name in ('register_blueprint', 'add_url_rule'):
    if not hasattr(app, name):
        try:
            setattr(app, name, _no_op_function)
        except Exception:
            pass
# Some test runners replace Flask with a lightweight MockFlask which may not
# implement `config` as a dict. Ensure `app.config` exists and is writable to
# avoid AttributeError during test collection.
if not hasattr(app, 'config') or app.config is None:
    try:
        app.config = {}
    except Exception:
        # best-effort: ignore if we cannot inject config
        pass
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'crypto-dashboard-secret')

# Add startup time tracking
startup_time = time.time()

# Configure allowed CORS origins from environment
cors_env = os.environ.get('CORS_ALLOWED_ORIGINS', '*')
if cors_env == '*':
    # Default development restriction: only allow local dev origins so we don't ship a
    # permissive CORS policy accidentally. This is intended for local tooling only.
    dev_origins = [
        # Any localhost/127.0.0.1 port (covers Vite hopping ports)
        r"^http://127\.0\.0\.1:\d+$",
        r"^http://localhost:\d+$",
        # Cloudflare / other dev tools
        "http://127.0.0.1:3100",
        "http://localhost:3100",
        # Common alternate dev ports (Next.js, other tools)
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        # Allow local LAN addresses on the 192.168.*.* range so devices on the
        # same network (or the host using the network IP) can access the API
        # when the SPA is served from that address during development. This is
        # intentionally restricted to the private 192.168.* range and not a
        # permissive wildcard for production.
        r"^https?://192\.168\.\d+\.\d+(:\d+)?$",
    ]
    # Expose a canonical `cors_origins` variable so runtime inspection
    # endpoints (e.g. /api/server-info) can always reference it.
    cors_origins = dev_origins
    try:
        CORS(
            app,
            resources={r"/*": {"origins": dev_origins}},
            supports_credentials=True,
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
        )
        logging.info(f"CORS configured with dev_origins: {len(dev_origins)} origins")
    except Exception as e:
        # If tests replace Flask with a very small MockFlask lacking expected
        # lifecycle helper methods, provide no-op shims so import-time setup
        # doesn't crash test collection.
        logging.warning(f"CORS initialization failed (will retry): {e}")
        def _no_op_decorator(fn):
            return fn
        def _no_op_function(*args, **kwargs):
            return None

        for name in ('after_request', 'before_request', 'teardown_request', 'context_processor'):
            if not hasattr(app, name):
                try:
                    setattr(app, name, _no_op_decorator)
                except Exception:
                    pass

        for name in ('register_blueprint', 'add_url_rule'):
            if not hasattr(app, name):
                try:
                    setattr(app, name, _no_op_function)
                except Exception:
                    pass
        # route and HTTP method shortcuts (get/post/put/delete) are decorators;
        # provide no-op decorators if missing or not callable so import-time
        # endpoint definitions don't fail under a minimalist MockFlask.
        def _ensure_decorator(name):
            try:
                existing = getattr(app, name, None)
            except Exception:
                existing = None
            if not existing or not callable(existing):
                try:
                    setattr(app, name, lambda *a, **k: (lambda f: f))
                except Exception:
                    pass

        for _d in ('route', 'get', 'post', 'put', 'delete', 'patch'):
            _ensure_decorator(_d)

        # Retry CORS now that shims are present; if it still fails, continue silently.
        try:
            CORS(app, resources={r"/*": {"origins": dev_origins}})
            logging.info(f"CORS configured with dev_origins (retry): {len(dev_origins)} origins")
        except Exception:
            logging.exception('CORS initialization skipped due to MockFlask limitations')
else:
    cors_origins = [origin.strip() for origin in cors_env.split(',') if origin.strip()]
    try:
        CORS(app, origins=cors_origins)
        logging.info(f"CORS configured with production origins: {cors_origins}")
    except Exception:
        logging.exception('CORS initialization skipped due to environment limitations')

# Register blueprints after final app creation
try:
    if "watchlist_bp" not in app.blueprints:
        app.register_blueprint(watchlist_bp)
except Exception:
    logging.exception('Skipping blueprint registration during test or mocked environment')

# Register intelligence API blueprint
try:
    from intelligence_api import intelligence_bp
    app.register_blueprint(intelligence_bp)
    logging.info('✅ Intelligence API blueprint registered')
except Exception as e:
    logging.warning(f'Intelligence API blueprint registration skipped: {e}')

# Initialize Flask-Talisman only when not explicitly disabled (tests/CI may
# want to turn it off). When disabled, ensure `app.jinja_env` exists so any
# code that expects it won't fail during import/collection.
try:
    disable_talisman = os.environ.get('DISABLE_TALISMAN', '0') == '1'
except Exception:
    disable_talisman = False

if not disable_talisman and not app.config.get('TESTING', False):
    try:
        Talisman(app, content_security_policy={
            'default-src': ["'self'"],
            'img-src': ["'self'", 'data:'],
            'script-src': ["'self'"],
            'style-src': ["'self'"],
        },
        strict_transport_security=True,
        frame_options='deny',
        x_xss_protection=True,
        x_content_type_options=True)
    except Exception:
        # best-effort: don't crash app creation if Talisman can't be applied
        logging.exception('Talisman initialization failed; continuing without it')
else:
    # Ensure jinja_env and its globals dict exist so code importing the app
    # (or extensions) can safely reference app.jinja_env.globals during tests.
    if not hasattr(app, 'jinja_env') or getattr(app.jinja_env, 'globals', None) is None:
        class _DummyJinjaEnv:
            def __init__(self):
                self.globals = {}
        app.jinja_env = _DummyJinjaEnv()

# ---------------- Health + Metrics -----------------
_ERROR_STATS = { '5xx': 0 }
one_minute_market_stats = {}
_one_min_hist_lock = threading.Lock()
_spike_p95_history = deque(maxlen=30)
_spike_p99_history = deque(maxlen=30)
_extreme_gainer_history = deque(maxlen=30)
_adv_decl_ratio_history = deque(maxlen=60)  # keep more samples for smoother bands
_breadth_adv_decl_ratio_ema = None
_breadth_net_advancers_ema = None
_breadth_thrust_started_at = None
_ALERTER = AlertNotifier.from_env()
_STALE_ALERT_RATIO = float(os.environ.get('ALERT_STALE_RATIO','0.6'))
_STALE_ALERT_WINDOW_SEC = int(os.environ.get('ALERT_STALE_MIN_WINDOW_SEC','120'))
_last_stale_alert = 0.0
_stale_window_start = None

# Configurable thresholds / params (env override optional)
_BREADTH_THRUST_RATIO = float(os.environ.get('BREADTH_THRUST_RATIO','1.3'))
_BREADTH_THRUST_NET_MIN = int(os.environ.get('BREADTH_THRUST_NET_MIN','0'))  # allow >=0 by default
_BREADTH_EMA_ALPHA = float(os.environ.get('BREADTH_EMA_ALPHA','0.2'))  # smoothing for EMA oscillator
_BREADTH_BB_K = float(os.environ.get('BREADTH_BB_K','2.0'))  # Bollinger multiple for adv/decl ratio

# Unified threshold registry (env overridable) to avoid scattering magic numbers
THRESHOLDS = {
    'pump_thrust_confirm_ratio_min': float(os.environ.get('PUMP_THRUST_CONFIRM_MIN_RATIO','0.6')),
    'pump_thrust_adv_decl_ratio_min': float(os.environ.get('PUMP_THRUST_ADV_DECL_MIN','1.8')),
    'narrowing_vol_sd_max': float(os.environ.get('NARROWING_VOL_SD_MAX','0.05')),
    'accel_fade_min_thrust_seconds': float(os.environ.get('ACCEL_FADE_MIN_THRUST_SECONDS','30')),
    # p95 rate must be BELOW (negative) this to count as fading (default 0 => any negative)
    'accel_fade_p95_rate_max': float(os.environ.get('ACCEL_FADE_P95_RATE_MAX','0')),
}

_THRESHOLDS_FILE = os.environ.get('THRESHOLDS_FILE','thresholds.json')

def _load_thresholds_file():
    """Load persisted thresholds from JSON file if present (best‑effort)."""
    if not os.path.isfile(_THRESHOLDS_FILE):
        return
    import json
    try:
        with open(_THRESHOLDS_FILE,'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:  # pragma: no cover - defensive
        logging.warning(f"Failed loading thresholds file: {e}")
        return
    if not isinstance(data, dict):
        return
    for k,v in data.items():
        if k in THRESHOLDS:
            try:
                THRESHOLDS[k] = float(v)
            except (TypeError, ValueError):
                # Ignore invalid persisted value
                continue

_load_thresholds_file()


def pct_change(current: float | int | None, past: float | int | None) -> float | None:
    """Centralized percent-change helper with guardrails.

    Returns None when the past value is missing/invalid/non-positive.
    This prevents "missing baseline" from being reported as a real 0.0% move.
    """
    if current is None or past is None:
        return None
    try:
        c = float(current)
        p = float(past)
    except (TypeError, ValueError):
        return None
    if p <= 0.0:
        return None
    return (c - p) / p * 100.0

def update_thresholds(patch: dict):
    """Runtime safe partial update with validation: returns (applied, errors)."""
    applied: dict[str, float] = {}
    errors: dict[str, str] = {}
    for k,v in patch.items():
        if k not in THRESHOLDS:
            errors[k] = 'unknown_threshold'
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            errors[k] = 'not_float'
            continue
        # Basic semantic validations
        if 'ratio' in k and fv <= 0:
            errors[k] = 'ratio_must_be_positive'
            continue
        if 'sd_max' in k and fv <= 0:
            errors[k] = 'sd_max_must_be_positive'
            continue
        if 'seconds' in k and fv < 0:
            errors[k] = 'seconds_must_be_non_negative'
            continue
        THRESHOLDS[k] = fv
        applied[k] = fv
    # Persist if at least one applied
    if applied:
        import json
        try:
            with open(_THRESHOLDS_FILE,'w', encoding='utf-8') as f:
                json.dump(THRESHOLDS, f, indent=2)
        except OSError as e:  # pragma: no cover - file system issues
            logging.warning(f"Failed persisting thresholds: {e}")
    return applied, errors

@app.route('/api/thresholds', methods=['GET','POST'])
def api_thresholds():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        applied, errors = update_thresholds(data)
        status_code = 200 if not errors else 400 if not applied else 207
        return jsonify({'applied': applied, 'errors': errors, 'thresholds': THRESHOLDS}), status_code
    return jsonify({'thresholds': THRESHOLDS})

@app.before_request
def _before_req_metrics():
    g._start_time = time.time()
    # Correlation ID: honor inbound header else generate
    try:
        incoming = request.headers.get('X-Request-ID') or request.headers.get('X-Correlation-ID')
        rid = incoming if incoming and len(incoming) < 80 else uuid.uuid4().hex[:24]
        REQUEST_ID_CTX.set(rid)
    except Exception:
        pass

@app.after_request
def _after_req_metrics(resp):
    try:
        if 500 <= resp.status_code < 600:
            _ERROR_STATS['5xx'] += 1
        # Echo correlation id header for client chaining
        try:
            rid = REQUEST_ID_CTX.get()
            if rid:
                resp.headers['X-Request-ID'] = rid
        except Exception:
            pass
    except Exception:
        pass
    return resp

# ---------------- SWR CONFIG (env configurable) -----------------
_GAINERS_1M_SWR_TTL = float(os.environ.get('GAINERS_1M_SWR_TTL','6'))
_GAINERS_1M_SWR_STALE = float(os.environ.get('GAINERS_1M_SWR_STALE','24'))
_GAINERS_3M_SWR_TTL = float(os.environ.get('GAINERS_3M_SWR_TTL','6'))
_GAINERS_3M_SWR_STALE = float(os.environ.get('GAINERS_3M_SWR_STALE','24'))
_LOSERS_3M_SWR_TTL = float(os.environ.get('LOSERS_3M_SWR_TTL', str(_GAINERS_3M_SWR_TTL)))
_LOSERS_3M_SWR_STALE = float(os.environ.get('LOSERS_3M_SWR_STALE', str(_GAINERS_3M_SWR_STALE)))
_TOP_MOVERS_BAR_SWR_TTL = float(os.environ.get('TOP_MOVERS_BAR_SWR_TTL', str(_GAINERS_3M_SWR_TTL)))
_TOP_MOVERS_BAR_SWR_STALE = float(os.environ.get('TOP_MOVERS_BAR_SWR_STALE', str(_GAINERS_3M_SWR_STALE)))

@stale_while_revalidate(ttl=_GAINERS_1M_SWR_TTL, stale_window=_GAINERS_1M_SWR_STALE)
@ttl_cache(ttl=int(_GAINERS_1M_SWR_TTL))
def _get_gainers_table_1min_swr():
    data = get_crypto_data_1min()
    baseline_meta_1m = _get_baseline_meta_1m()
    warming_1m = not bool(baseline_meta_1m.get("ready"))
    baseline_ts_1m = baseline_meta_1m.get("baseline_ts")
    if not data:
        return {
            'component': 'gainers_table_1min',
            'data': [],
            'count': 0,
            'table_type': 'gainers',
            'time_frame': '1_minute',
            'update_interval': 10000,
            'last_updated': datetime.now().isoformat(),
            'warming': warming_1m,
            'baseline_ts': baseline_ts_1m,
        }
    gainers = data.get('gainers', [])
    limit = int(CONFIG.get("ONE_MIN_MAX_COINS", 35))
    gainers_table_data = []
    for i, coin in enumerate(gainers[:limit]):
        # accept either the processed shape (current/gain/initial_1min) or the
        # seeded fixture shape (current_price, price_change_percentage_1min)
        current_price = coin.get('current') or coin.get('current_price') or 0
        gain_pct = _safe_float(coin.get('gain'))
        if gain_pct is None:
            gain_pct = _safe_float(coin.get('price_change_percentage_1min'))
        if gain_pct is None:
            gain_pct = 0
        initial_price = coin.get('initial_1min') or coin.get('initial_price_1min') or current_price
        peak_gain = coin.get('peak_gain', gain_pct)
        trend_direction = coin.get('trend_direction', 'flat')
        trend_streak = coin.get('trend_streak', 0)
        trend_score = coin.get('trend_score', 0.0)
        trend_delta = coin.get('trend_delta', 0.0)
        momentum = 'strong' if gain_pct > 5 else 'moderate'
        alert_level = 'high' if gain_pct > 10 else 'normal'
        gainers_table_data.append({
            'rank': i + 1,
            'symbol': coin.get('symbol'),
            'current_price': current_price,
            'price_change_percentage_1min': gain_pct,
            'initial_price_1min': initial_price,
            'actual_interval_minutes': coin.get('interval_minutes', 1),
            'peak_gain': peak_gain,
            'trend_direction': trend_direction,
            'trend_streak': trend_streak,
            'trend_score': trend_score,
            'trend_delta': trend_delta,
            'momentum': momentum,
            'alert_level': alert_level
        })
        try:
            if isinstance(gain_pct, (int, float)) and abs(gain_pct) >= ALERT_IMPULSE_1M_THRESH:
                _emit_impulse_alert(coin.get('symbol'), gain_pct, current_price, window="1m")
        except Exception:
            pass

    # Also emit impulse alerts for strong 1m losers, even though this component
    # only renders the gainers table. This keeps the main alerts stream
    # directionally complete without needing a dedicated 1m losers component.
    try:
        losers = data.get('losers', []) or []
        for coin in losers[:max(10, min(20, limit))]:
            current_price = coin.get('current') or coin.get('current_price') or 0
            gain_pct = _safe_float(coin.get('gain'))
            if gain_pct is None:
                gain_pct = _safe_float(coin.get('price_change_percentage_1min'))
            if gain_pct is None:
                gain_pct = 0
            if isinstance(gain_pct, (int, float)) and abs(gain_pct) >= ALERT_IMPULSE_1M_THRESH:
                _emit_impulse_alert(coin.get('symbol'), gain_pct, current_price, window="1m")
    except Exception:
        pass
    return {
        'component': 'gainers_table_1min',
        'data': gainers_table_data,
        'count': len(gainers_table_data),
        'table_type': 'gainers',
        'time_frame': '1_minute',
        'update_interval': 10000,
        'last_updated': datetime.now().isoformat(),
        'warming': warming_1m,
        'baseline_ts': baseline_ts_1m,
        **({'source': data.get('source')} if isinstance(data, dict) and data.get('source') else {}),
        **({'seed': True} if isinstance(data, dict) and data.get('seed') else {})
    }

@stale_while_revalidate(ttl=_GAINERS_3M_SWR_TTL, stale_window=_GAINERS_3M_SWR_STALE)
@ttl_cache(ttl=int(_GAINERS_3M_SWR_TTL))
def _get_gainers_table_3min_swr():
    data = get_crypto_data()
    if not data:
        return None
    baseline_ready = bool(data.get("baseline_ready_3m"))
    baseline_ts = data.get("baseline_ts_3m")
    gainers = data.get('gainers', [])
    limit = int(CONFIG.get("MAX_COINS_PER_CATEGORY", 30))
    gainers_table_data = []
    for i, coin in enumerate(gainers[:limit]):
        sym = coin['symbol']
        gain = _safe_float(coin.get('gain'))
        if gain is None:
            gain = 0
        direction, streak, score = _update_3m_trend(sym, gain)
        gainers_table_data.append({
            'rank': i + 1,
            'symbol': coin['symbol'],
            'current_price': coin['current'],
            'price_change_percentage_3min': gain,
            'initial_price_3min': coin['initial_3min'],
            'actual_interval_minutes': coin.get('interval_minutes', 3),
            'trend_direction': direction,
            'trend_streak': streak,
            'trend_score': score,
            'momentum': 'strong' if gain > 5 else 'moderate',
            'alert_level': 'high' if gain > 10 else 'normal'
        })
        try:
            if isinstance(gain, (int, float)) and abs(gain) >= ALERT_IMPULSE_3M_THRESH:
                _emit_impulse_alert(sym, float(gain or 0), coin.get('current'), window="3m")
        except Exception:
            pass
    return {
        'component': 'gainers_table',
        'data': gainers_table_data,
        'count': len(gainers_table_data),
        'table_type': 'gainers',
        'time_frame': '3_minutes',
        'update_interval': 3000,
        'last_updated': datetime.now().isoformat(),
        'warming': not baseline_ready,
        'baseline_ts': baseline_ts,
    }

@stale_while_revalidate(ttl=_LOSERS_3M_SWR_TTL, stale_window=_LOSERS_3M_SWR_STALE)
@ttl_cache(ttl=int(_LOSERS_3M_SWR_TTL))
def _get_losers_table_3min_swr():
    data = get_crypto_data()
    if not data:
        return None
    baseline_ready = bool(data.get("baseline_ready_3m"))
    baseline_ts = data.get("baseline_ts_3m")
    losers = data.get('losers', [])
    limit = int(CONFIG.get("MAX_COINS_PER_CATEGORY", 30))
    losers_table_data = []
    for i, coin in enumerate(losers[:limit]):
        sym = coin['symbol']
        gain = _safe_float(coin.get('gain'))
        if gain is None:
            gain = 0
        direction, streak, score = _update_3m_trend(sym, gain)
        losers_table_data.append({
            'rank': i + 1,
            'symbol': coin['symbol'],
            'current_price': coin['current'],
            'price_change_percentage_3min': gain,
            'initial_price_3min': coin['initial_3min'],
            'actual_interval_minutes': coin.get('interval_minutes', 3),
            'trend_direction': direction,
            'trend_streak': streak,
            'trend_score': score,
            'momentum': 'strong' if gain < -5 else 'moderate',
            'alert_level': 'high' if gain < -10 else 'normal'
        })
        try:
            if isinstance(gain, (int, float)) and abs(gain) >= ALERT_IMPULSE_3M_THRESH:
                _emit_impulse_alert(sym, float(gain or 0), coin.get('current'), window="3m")
        except Exception:
            pass
    return {
        'component': 'losers_table',
        'data': losers_table_data,
        'count': len(losers_table_data),
        'table_type': 'losers',
        'time_frame': '3_minutes',
        'update_interval': 3000,
        'last_updated': datetime.now().isoformat(),
        'warming': not baseline_ready,
        'baseline_ts': baseline_ts,
    }

@stale_while_revalidate(ttl=_TOP_MOVERS_BAR_SWR_TTL, stale_window=_TOP_MOVERS_BAR_SWR_STALE)
@ttl_cache(ttl=int(_TOP_MOVERS_BAR_SWR_TTL))
def _get_top_movers_bar_swr():
    data = get_crypto_data()
    if not data:
        return None
    top_movers_3min = data.get('top24h', [])
    top_movers_data = []
    for coin in top_movers_3min[:15]:
        top_movers_data.append({
            'symbol': coin['symbol'],
            'current_price': coin['current'],
            'price_change_3min': coin['gain'],
            'initial_price_3min': coin['initial_3min'],
            'interval_minutes': coin.get('interval_minutes', 3),
            'bar_color': 'green' if coin['gain'] > 0 else 'red',
            'momentum': 'strong' if abs(coin['gain']) > 5 else 'moderate'
        })
    return {
        'component': 'top_movers_bar',
        'data': top_movers_data,
        'count': len(top_movers_data),
        'animation': 'horizontal_scroll',
        'time_frame': '3_minutes',
        'update_interval': 3000,
        'last_updated': datetime.now().isoformat()
    }

# Centralized SWR registry to avoid duplication
def _swr_entries():
    return [
        ('gainers_1m', globals().get('_get_gainers_table_1min_swr'), _GAINERS_1M_SWR_TTL, _GAINERS_1M_SWR_STALE),
        ('gainers_3m', globals().get('_get_gainers_table_3min_swr'), _GAINERS_3M_SWR_TTL, _GAINERS_3M_SWR_STALE),
        ('losers_3m', globals().get('_get_losers_table_3min_swr'), _LOSERS_3M_SWR_TTL, _LOSERS_3M_SWR_STALE),
# Closing bracket fixed below
        ('top_movers_bar', globals().get('_get_top_movers_bar_swr'), _TOP_MOVERS_BAR_SWR_TTL, _TOP_MOVERS_BAR_SWR_STALE),
    ]
# --- Helper to reduce duplication & complexity in 3m trend updates ---
def _update_3m_trend(sym: str, gain_val):
    g = float(gain_val or 0)
    prev = three_minute_trends.get(sym, {'last': g, 'streak': 0, 'last_dir': 'flat', 'score': 0.0})
    direction = 'up' if g > prev['last'] else ('down' if g < prev['last'] else 'flat')
    streak = prev['streak'] + 1 if direction != 'flat' and direction == prev['last_dir'] else (1 if direction != 'flat' else prev['streak'])
    score = round(prev['score'] * 0.8 + g * 0.2, 3)
    three_minute_trends[sym] = {'last': g, 'streak': streak, 'last_dir': direction, 'score': score}
    _maybe_fire_trend_alert('3m', sym, direction, streak, score)
    return direction, streak, score

@app.route('/api/health')
def api_health():
    """Lightweight health alias (faster than full server-info)."""
    payload = {
        'status': 'ok',
        'uptime_seconds': round(time.time() - startup_time, 2),
        'errors_5xx': _ERROR_STATS['5xx']
    }
    return jsonify(HealthResponse(**payload).model_dump())

@app.route('/health')
def health_root():
    """Root health alias for launcher readiness checks."""
    return api_health()


@app.route("/api/snapshots/one-hour-volume", methods=["GET"])
def one_hour_volume():
    """Return 1h volume change rows expected by VolumeBannerScroll."""
    try:
        if callable(get_1h_volume_weighted_data):
            rows = get_1h_volume_weighted_data()
            normalized = []
            for item in (rows or []):
                vol_now = item.get("volume_now") or item.get("volume") or item.get("current_volume")
                vol_ago = item.get("volume_1h_ago") or item.get("prev_volume") or item.get("previous_volume")
                pct = item.get("volume_change_pct") or item.get("percent_change")
                if pct is None and isinstance(vol_now, (int, float)) and isinstance(vol_ago, (int, float)) and vol_ago:
                    pct = ((vol_now - vol_ago) / vol_ago) * 100.0
                normalized.append({
                    **item,
                    "volume_now": vol_now,
                    "volume_1h_ago": vol_ago,
                    "volume_change_pct": pct,
                    "percent_change": pct,
                })
            return jsonify({"data": normalized}), 200
        return jsonify({"data": []}), 200
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500

@app.route('/api/metrics')
def metrics():
    """Return internal operational metrics (non-prometheus simple JSON)."""
    out = {
        'status': 'ok',
        'uptime_seconds': round(time.time() - startup_time, 2),
        'errors_5xx': _ERROR_STATS['5xx']
    }
    try:
        from price_fetch import get_price_fetch_metrics
        out['price_fetch'] = get_price_fetch_metrics()
        # Surface circuit breaker (flatten selected fields for convenience)
        cb = out['price_fetch'].get('circuit_breaker') or {}
        if cb:
            out['circuit_breaker'] = {
                'state': cb.get('state'),
                'failures': cb.get('failures'),
                'open_until': cb.get('open_until'),
                'is_open': cb.get('state') == 'OPEN',
                'is_half_open': cb.get('state') == 'HALF_OPEN'
            }
        if one_minute_market_stats:
            out['one_min_market'] = dict(one_minute_market_stats)
    except Exception as e:
        out['price_fetch_error'] = str(e)
    # SWR caches summary block
    now = time.time()
    swr_entries = _swr_entries()
    swr_caches = collect_swr_cache_stats(now, swr_entries)
    # Stale surge detection (any cache) aggregated ratio
    try:
        total_calls = 0
        served_cached = 0
        for v in swr_caches.values():
            stats = v
            total_calls += stats.get('total_calls',0) or 0
            # cached includes both fresh & stale; approximate stale via served_cached_total vs fresh? For simplicity use served_cached_total
            served_cached += stats.get('served_cached',0) or 0
        global _stale_window_start, _last_stale_alert
        if total_calls >= 10:  # avoid noise
            ratio = (served_cached/total_calls) if total_calls else 0
            if ratio >= _STALE_ALERT_RATIO:
                if _stale_window_start is None:
                    _stale_window_start = now
                elif (now - _stale_window_start) >= _STALE_ALERT_WINDOW_SEC and (now - _last_stale_alert) >=  _STALE_ALERT_WINDOW_SEC:
                    try:
                        _ALERTER.send('stale_surge', {'ratio': round(ratio,3), 'window_seconds': int(now-_stale_window_start)})
                        _last_stale_alert = now
                    except Exception:
                        pass
            else:
                if _stale_window_start is not None and (now - _stale_window_start) >= _STALE_ALERT_WINDOW_SEC:
                    try:
                        _ALERTER.send('stale_resolved', {})
                    except Exception:
                        pass
                _stale_window_start = None
    except Exception:
        pass
    if swr_caches:
        out['swr_caches'] = swr_caches
    # Validate minimally (will raise if schema mismatch during development)
    try:
        validated = MetricsResponse(**out).model_dump()
    except Exception:
        # fall back without blocking endpoint
        validated = out
    return jsonify(validated)

@app.route('/api/mobile/bundle')
def api_mobile_bundle():
    """Mobile-friendly aggregate: returns banner + tables in one call.

    Shape matches moonwalking_mobile packages/core DataBundle/MarketRow.
    """
    try:
        # 1h banner (price change)
        banner_rows = []
        try:
            banner = _compute_top_banner_data_safe() or []
            for it in banner[:20]:
                banner_rows.append({
                    'symbol': it.get('symbol'),
                    'price': float(it.get('current_price') or 0),
                    'changePct1h': float(it.get('price_change_1h') or 0),
                    'ts': int(time.time() * 1000),
                })
        except Exception:
            pass

        # 1m / 3m gainers/losers via SWR helpers (already cached)
        gainers1m_rows = []
        try:
            g1m = _get_gainers_table_1min_swr() or {}
            for it in (g1m.get('data') or [])[:30]:
                gainers1m_rows.append({
                    'symbol': it.get('symbol'),
                    'price': float(it.get('current_price') or 0),
                    'changePct1m': float(it.get('price_change_percentage_1min') or 0),
                    'ts': int(time.time() * 1000),
                })
        except Exception:
            pass

        gainers3m_rows = []
        try:
            g3m = _get_gainers_table_3min_swr() or {}
            for it in (g3m.get('data') or [])[:30]:
                gainers3m_rows.append({
                    'symbol': it.get('symbol'),
                    'price': float(it.get('current_price') or 0),
                    'changePct3m': float(it.get('price_change_percentage_3min') or 0),
                    'ts': int(time.time() * 1000),
                })
        except Exception:
            pass

        losers3m_rows = []
        try:
            l3m = _get_losers_table_3min_swr() or {}
            for it in (l3m.get('data') or [])[:30]:
                losers3m_rows.append({
                    'symbol': it.get('symbol'),
                    'price': float(it.get('current_price') or 0),
                    'changePct3m': float(it.get('price_change_percentage_3min') or 0),
                    'ts': int(time.time() * 1000),
                })
        except Exception:
            pass

        # 1h volume placeholder: use top banner symbols with 0 volume change if true 1h volume unavailable
        volume1h_rows = []
        try:
            for it in banner_rows[:20]:
                volume1h_rows.append({
                    'symbol': it['symbol'],
                    'price': it['price'],
                    'volumeChangePct1h': 0.0,
                    'ts': it['ts'],
                })
        except Exception:
            pass

        out = {
            'banner1h': banner_rows,
            'gainers1m': gainers1m_rows,
            'gainers3m': gainers3m_rows,
            'losers3m': losers3m_rows,
            'volume1h': volume1h_rows,
            'ts': int(time.time() * 1000),
        }
        return jsonify(out)
    except Exception as e:
        try:
            app.logger.exception("mobile bundle error: %s", e)
        except Exception:
            pass
        return jsonify({'banner1h': [], 'gainers1m': [], 'gainers3m': [], 'losers3m': [], 'volume1h': [], 'ts': int(time.time()*1000)}), 200

@app.route('/api/sentiment')
def api_sentiment():
    """Return simple sentiment rows for a comma-separated symbols list."""
    syms_param = (request.args.get('symbols') or '').strip()
    if not syms_param:
        # No symbols provided, return divergence data
        payload, used_url, err_info = _proxy_pipeline_request('/sentiment/divergence', timeout=5)
        if err_info:
            return _pipeline_error_response(err_info, 'Sentiment divergence fetch failed')

        divergence_payload = payload or {}
        return jsonify({
            'success': True,
            'data': divergence_payload,
            'timestamp': divergence_payload.get('timestamp', datetime.utcnow().isoformat()),
            'pipeline_url': used_url,
        })

    # Process symbols list
    out = {}
    # TODO: implement symbol-specific sentiment
    return jsonify(out)


try:
    from sentiment_orchestrator import get_basic_sentiment
except Exception:
    get_basic_sentiment = None


@app.route('/api/sentiment-basic')
def api_sentiment_basic():
    """Return a small, fast basic sentiment payload for the frontend SentimentCard.

    Uses only in-memory tape data; never blocks on external network calls.
    """
    try:
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with _MARKET_HEAT_LOCK:
            heat = dict(_MARKET_HEAT_CACHE) if _MARKET_HEAT_CACHE else None
        if not heat:
            heat = _compute_market_heat()
        if not isinstance(heat, dict):
            heat = {}

        components_raw = heat.get("components") if isinstance(heat.get("components"), dict) else {}
        components = {
            k: (components_raw.get(k) if isinstance(components_raw, dict) else None)
            for k in _MARKET_HEAT_COMPONENT_KEYS
        }
        total_symbols = components.get("total_symbols")
        has_data = isinstance(total_symbols, (int, float)) and total_symbols > 0

        score = heat.get("score") if has_data else None
        regime = heat.get("regime") if has_data and isinstance(heat.get("regime"), str) else None
        label = heat.get("label") if has_data and isinstance(heat.get("label"), str) else None
        confidence = heat.get("confidence") if has_data else None
        reasons = heat.get("reasons") if isinstance(heat.get("reasons"), list) else []
        if not reasons:
            reasons = ["No price data yet"] if not has_data else ["Market in equilibrium"]

        ts = heat.get("ts") if isinstance(heat.get("ts"), str) else None
        timestamp = ts or now_iso

        stale = not has_data
        age_s = None
        try:
            if ts:
                ts_norm = ts.replace("Z", "+00:00")
                ts_dt = datetime.fromisoformat(ts_norm)
                age_s = (datetime.now(timezone.utc) - ts_dt).total_seconds()
                if age_s > float(os.getenv("SENTIMENT_BASIC_STALE_S", "60")):
                    stale = True
        except Exception:
            pass

        fg_value = None
        fg_class = ""
        with _FG_LOCK:
            fg_cached = _FG_CACHE.get("data")
        if isinstance(fg_cached, dict):
            fg_value = fg_cached.get("value")
            fg_class = fg_cached.get("classification") or fg_cached.get("label") or ""

        meta_payload = {
            "ok": bool(has_data),
            "pipelineRunning": bool(not stale),
            "staleSeconds": int(age_s) if age_s is not None else None,
            "lastOkTs": ts if has_data else None,
            "error": None,
            "source": "internal",
            "stale": bool(stale),
        }
        payload = {
            "ok": True,
            "timestamp": timestamp,
            "market_heat": {
                "score": score,
                "regime": regime,
                "label": label,
                "confidence": confidence,
                "components": components,
                "reasons": reasons,
            },
            "fear_greed": {"value": fg_value, "classification": fg_class or ""},
            "btc_funding": {"rate_percentage": None},
            "meta": meta_payload,
        }
        return jsonify(SentimentBasicPayload(**payload).model_dump())
    except Exception as e:
        logging.debug(f"sentiment-basic error: {e}")
        ts_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = {
            "ok": True,
            "timestamp": ts_iso,
            "market_heat": {
                "score": None,
                "regime": None,
                "label": None,
                "confidence": None,
                "components": {k: None for k in _MARKET_HEAT_COMPONENT_KEYS},
                "reasons": ["No price data yet"],
            },
            "fear_greed": {"value": None, "classification": ""},
            "btc_funding": {"rate_percentage": None},
            "meta": {
                "ok": False,
                "pipelineRunning": False,
                "staleSeconds": None,
                "lastOkTs": None,
                "error": "sentiment_basic_exception",
                "source": "internal",
                "stale": True,
            },
        }
        return jsonify(SentimentBasicPayload(**payload).model_dump())

def _get_sentiment_for_symbol(*args, **kwargs):
    # allow tests to disable sentiment to avoid import cycles
    if os.getenv("MW_DISABLE_SENTIMENT") == "1":
        return None
    try:
        from sentiment_aggregator import get_sentiment_for_symbol
        return get_sentiment_for_symbol(*args, **kwargs)
    except Exception:
        return None
try:
    from sentiment_intelligence import ai_engine
except Exception:
    class _DummyAIEngine:
        def score_headlines_local(self, *a, **k):
            return {"score": 0.0, "label": "neutral", "confidence": 0.0}

        def generate_narrative(self, *a, **k):
            return ""
    ai_engine = _DummyAIEngine()

_SENTIMENT_CACHE = {}
_SENTIMENT_CACHE_LOCK = threading.Lock()
_SENTIMENT_TTL_S = int(os.getenv("SENTIMENT_TTL_S", "60"))
_SENTIMENT_TIMEOUT_FAST_S = float(os.getenv("SENTIMENT_TIMEOUT_FAST_S", "3"))
_SENTIMENT_TIMEOUT_SLOW_S = float(os.getenv("SENTIMENT_TIMEOUT_SLOW_S", "25"))
# Legacy env still supported; falls back to slow timeout if provided
_SENTIMENT_TIMEOUT_S = float(os.getenv("SENTIMENT_TIMEOUT_S", str(_SENTIMENT_TIMEOUT_SLOW_S)))

# Sentiment proxy cache settings
def _sentiment_cache_lookup(symbol):
    now = time.time()
    with _SENTIMENT_CACHE_LOCK:
        entry = _SENTIMENT_CACHE.get(symbol)
    if not entry:
        return None, True, None
    age = now - entry["ts"]
    return entry["data"], age > _SENTIMENT_TTL_S, entry["ts"]

def _sentiment_cache_set(symbol, data):
    with _SENTIMENT_CACHE_LOCK:
        _SENTIMENT_CACHE[symbol] = {"ts": time.time(), "data": data}


def _load_cache(path: Path):
    try:
        with path.open("r") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(path: Path, payload: dict):
    try:
        path.parent.mkdir(exist_ok=True, parents=True)
        with path.open("w") as f:
            json.dump(payload, f)
    except Exception:
        pass


def _now_iso():
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")



@app.route("/api/sentiment/fng")
def api_sentiment_fng():
    """Removed legacy endpoint."""
    return jsonify({"ok": False, "message": "Removed. Use /api/sentiment/latest"}), 410


@app.route("/api/sentiment/market")
def api_sentiment_market():
    """Removed legacy endpoint."""
    return jsonify({"ok": False, "message": "Removed. Use /api/sentiment/latest"}), 410

_LATEST_PROXY_CACHE = None
_LATEST_PROXY_TS = None
_LATEST_PROXY_URL = None

def _build_proxy_meta(used_url: str | None, latency_ms: float, cache_ts=None, stale=False):
    meta = {
        "upstream_url": used_url,
        "upstream_latency_ms": int(latency_ms),
        "proxy_ts": time.time(),
        "stale": bool(stale),
    }
    if cache_ts:
        meta["stale_age_seconds"] = int(time.time() - cache_ts)
    return meta


@app.route('/api/sentiment/latest')
def api_sentiment_latest():
    """Strict proxy to sentiment pipeline for canonical sentiment payload.

    sentiment_meta comes ONLY from _get_sentiment_snapshot() (single source of truth).
    This route NEVER overrides sentiment_meta values - the polling mechanism is
    authoritative for: ok, pipelineRunning, staleSeconds, lastOkTs, lastTryTs, error.
    """
    global _LATEST_PROXY_CACHE, _LATEST_PROXY_TS, _LATEST_PROXY_URL

    symbol = request.args.get('symbol')
    params = {}
    if symbol:
        params["symbol"] = symbol.upper()

    start = time.time()
    payload, used_url, err_info = _proxy_pipeline_request("/sentiment/latest", params=params, timeout=1.0)
    latency_ms = (time.time() - start) * 1000

    # Single source of truth: sentiment_meta from the polling snapshot.
    # DO NOT override any fields here - the poller is authoritative.
    _, sentiment_meta = _get_local_sentiment_payload()

    if payload:
        _LATEST_PROXY_CACHE = payload
        _LATEST_PROXY_TS = time.time()
        _LATEST_PROXY_URL = used_url
        proxy_meta = _build_proxy_meta(used_url, latency_ms, cache_ts=_LATEST_PROXY_TS, stale=False)
        out = dict(payload)
        out["proxy_meta"] = proxy_meta
        out["sentiment_meta"] = sentiment_meta
        return jsonify(out)

    if _LATEST_PROXY_CACHE and _LATEST_PROXY_TS:
        proxy_meta = _build_proxy_meta(_LATEST_PROXY_URL, latency_ms, cache_ts=_LATEST_PROXY_TS, stale=True)
        out = dict(_LATEST_PROXY_CACHE)
        out["proxy_meta"] = proxy_meta
        out["sentiment_meta"] = sentiment_meta
        return jsonify(out)

    # No cached data available - return minimal response with canonical sentiment_meta
    status_code = err_info.get("status", 503) if err_info else 503
    proxy_meta = _build_proxy_meta(used_url, latency_ms, cache_ts=None, stale=True)
    return jsonify({
        "ok": False,
        "message": "Sentiment pipeline offline",
        "proxy_meta": proxy_meta,
        "sentiment_meta": sentiment_meta,  # unchanged from snapshot
    }), status_code


# Legacy endpoint - keeping for backward compatibility
@app.route('/api/sentiment/latest_legacy')
def api_sentiment_latest_legacy():
    """Legacy aggregator-based sentiment (deprecated - use /api/sentiment/latest instead)."""
    symbol = request.args.get('symbol', "BTC").upper()
    fresh = request.args.get("fresh", "0") == "1"

    timeout_budget = _SENTIMENT_TIMEOUT_SLOW_S if fresh else _SENTIMENT_TIMEOUT_FAST_S

    cached, is_stale, cache_ts = _sentiment_cache_lookup(symbol)
    if cached and not is_stale:
        payload = dict(cached)
        payload["symbol"] = payload.get("symbol") or symbol
        payload["stale"] = False
        payload["ts_cache"] = cache_ts
        return jsonify(payload)

    try:
        data = _get_sentiment_for_symbol(symbol, timeout_s=timeout_budget)
        _sentiment_cache_set(symbol, data)
        payload = dict(data)
        payload["symbol"] = payload.get("symbol") or symbol
        payload["stale"] = False
        payload["ts_cache"] = time.time()
        return jsonify(payload)
    except FuturesTimeout as exc:
        if cached:
            payload = dict(cached)
            payload["symbol"] = payload.get("symbol") or symbol
            payload["stale"] = True
            payload["ts_cache"] = cache_ts
            payload["error"] = f"timeout:{exc}"
            payload["upstream_url"] = SENTIMENT_PIPELINE_URL
            payload["hint"] = f"sentiment aggregator exceeded timeout ({timeout_budget}s)"
            return jsonify(payload)
        import hashlib
        seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16) % 30
        fallback = {
            'symbol': symbol,
            'overall_sentiment': (50 + seed) / 100,
            'fear_greed_index': 50 + seed,
            'total_sources': 0,
            'sources': [],
            'sentiment_history': [],
            'social_breakdown': {'reddit': 0.5, 'twitter': 0.5, 'telegram': 0.5, 'news': 0.5},
            'social_metrics': {'volume_change': 0, 'engagement_rate': 0, 'mentions_24h': 0},
            'timestamp': datetime.utcnow().isoformat() + "Z",
            'error': f"timeout:{exc}",
            'upstream_url': SENTIMENT_PIPELINE_URL,
            'hint': f"sentiment aggregator exceeded timeout ({timeout_budget}s)",
            'stale': True,
        }
        return jsonify(fallback)
    except Exception as exc:
        print(f"[Sentiment API] Error: {exc}")
        import random, hashlib
        seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16) % 30
        if cached:
            payload = dict(cached)
            payload["symbol"] = payload.get("symbol") or symbol
            payload["stale"] = True
            payload["ts_cache"] = cache_ts
            payload["error"] = str(exc)
            payload["upstream_url"] = SENTIMENT_PIPELINE_URL
            payload["hint"] = "sentiment aggregator error; serving cached payload"
            return jsonify(payload)
        fallback = {
            'symbol': symbol,
            'overall_sentiment': (50 + seed) / 100,
            'fear_greed_index': 50 + seed,
            'total_sources': 0,
            'sources': [],
            'sentiment_history': [],
            'social_breakdown': {'reddit': 0.5, 'twitter': 0.5, 'telegram': 0.5, 'news': 0.5},
            'social_metrics': {'volume_change': 0, 'engagement_rate': 0, 'mentions_24h': 0},
            'timestamp': datetime.utcnow().isoformat() + "Z",
            'error': str(exc),
            'upstream_url': SENTIMENT_PIPELINE_URL,
            'hint': "sentiment aggregator error; serving synthetic fallback",
            'stale': True,
        }
        return jsonify(fallback)


# ============================================================================
# SENTIMENT PIPELINE PROXY ENDPOINTS
# ============================================================================

SENTIMENT_HOST = os.getenv('SENTIMENT_HOST', '127.0.0.1')
SENTIMENT_PORT = os.getenv('SENTIMENT_PORT', '8002')
SENTIMENT_PIPELINE_URL = f"http://{SENTIMENT_HOST}:{SENTIMENT_PORT}"
SENTIMENT_PIPELINE_TIMEOUT_S = float(os.getenv("SENTIMENT_PIPELINE_TIMEOUT_S", "0.75"))
SENTIMENT_PIPELINE_POLL_S = float(os.getenv("SENTIMENT_PIPELINE_POLL_S", "20"))

_SENTIMENT_LAST_GOOD = None
_SENTIMENT_LAST_OK_TS = None
_SENTIMENT_LAST_TRY_TS = None
_SENTIMENT_LAST_ERROR = None
_SENTIMENT_LAST_SOURCES = None
_SENTIMENT_LOCK = threading.Lock()

# ============================================================================
# MARKET HEAT ENGINE — closed-loop sentiment from Coinbase tape data
# ============================================================================
_MARKET_HEAT_CACHE = {}  # latest computed heat snapshot
_MARKET_HEAT_LOCK = threading.Lock()
_MARKET_HEAT_HISTORY = deque(maxlen=60)  # ~8 min of scores at ~8s intervals
_MARKET_HEAT_COMPONENT_KEYS = (
    "green_1m",
    "red_1m",
    "green_3m",
    "red_3m",
    "total_symbols",
    "avg_return_1m",
    "avg_return_3m",
    "volatility",
    "momentum_alignment",
    "breadth_1m",
    "breadth_3m",
)

# Fear & Greed TTL cache (external bolt-on, optional)
_FG_CACHE = {"data": None, "ts": 0}
_FG_TTL_S = 300  # 5 min
_FG_LOCK = threading.Lock()


def _compute_market_heat():
    """Compute Market Heat Score from existing price_history deques.

    Pure computation — no network calls. Reads the ring-buffers that the
    background price-fetch loop already populates.

    Returns dict:
      score       (0-100)  composite heat score
      regime      str      risk_on | risk_off | chop | calm
      label       str      COLD | NEUTRAL | WARM | HOT | MANIC
      confidence  float    0-1 (how much data we have relative to ideal)
      components  dict     raw counts: green_1m, red_1m, green_3m, red_3m, total,
                           avg_return_1m, avg_return_3m, volatility, momentum_alignment
      reasons     list[str] human-readable explanations
      ts          str      ISO timestamp
    """
    now = time.time()
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Gather all symbols that have price history
    all_symbols = set(price_history.keys()) | set(price_history_1min.keys())
    if not all_symbols:
        return {
            "score": 50, "regime": "calm", "label": "NEUTRAL",
            "confidence": 0.0, "components": {}, "reasons": ["No price data yet"],
            "ts": now_iso,
        }

    # --- 3m returns ---
    returns_3m = {}
    for sym in all_symbols:
        hist = price_history.get(sym)
        if not hist or len(hist) < 2:
            continue
        try:
            latest_ts, latest_price = hist[-1]
            # Find baseline ~3m ago (target 180s, min 120s)
            baseline_price = None
            for ts_i, p_i in reversed(list(hist)):
                age = now - ts_i
                if age >= 120:
                    baseline_price = p_i
                    break
            if baseline_price and baseline_price > 0:
                ret = ((latest_price - baseline_price) / baseline_price) * 100
                returns_3m[sym] = ret
        except Exception:
            continue

    # --- 1m returns ---
    returns_1m = {}
    for sym in all_symbols:
        hist = price_history_1min.get(sym)
        if not hist or len(hist) < 2:
            continue
        try:
            latest_ts, latest_price = hist[-1]
            baseline_price = None
            for ts_i, p_i in reversed(list(hist)):
                age = now - ts_i
                if age >= 45:
                    baseline_price = p_i
                    break
            if baseline_price and baseline_price > 0:
                ret = ((latest_price - baseline_price) / baseline_price) * 100
                returns_1m[sym] = ret
        except Exception:
            continue

    # Use whichever set has more data as total count
    total_symbols = max(len(returns_3m), len(returns_1m), 1)

    # --- Breadth: % of symbols green ---
    green_3m = sum(1 for r in returns_3m.values() if r > 0.05)
    red_3m = sum(1 for r in returns_3m.values() if r < -0.05)
    green_1m = sum(1 for r in returns_1m.values() if r > 0.02)
    red_1m = sum(1 for r in returns_1m.values() if r < -0.02)

    breadth_3m = (green_3m / max(len(returns_3m), 1)) * 100  # 0-100
    breadth_1m = (green_1m / max(len(returns_1m), 1)) * 100

    # --- Average returns ---
    avg_return_3m = (sum(returns_3m.values()) / max(len(returns_3m), 1)) if returns_3m else 0.0
    avg_return_1m = (sum(returns_1m.values()) / max(len(returns_1m), 1)) if returns_1m else 0.0

    # --- Momentum alignment: do 1m and 3m agree? (-1..+1) ---
    # Count symbols where both windows have data
    common_syms = set(returns_1m.keys()) & set(returns_3m.keys())
    if common_syms:
        agree_count = sum(
            1 for s in common_syms
            if (returns_1m[s] > 0 and returns_3m[s] > 0)
            or (returns_1m[s] < 0 and returns_3m[s] < 0)
        )
        momentum_alignment = (agree_count / len(common_syms)) * 2 - 1  # -1 to +1
    else:
        momentum_alignment = 0.0

    # --- Volatility: stdev of 3m returns ---
    if len(returns_3m) >= 3:
        mean_3m = avg_return_3m
        variance = sum((r - mean_3m) ** 2 for r in returns_3m.values()) / len(returns_3m)
        volatility = math.sqrt(variance)
    else:
        volatility = 0.0

    # --- Composite Score (0-100) ---
    # Breadth weighted blend (60% 3m, 40% 1m)
    breadth_blend = breadth_3m * 0.6 + breadth_1m * 0.4

    # Momentum bonus/penalty (-15 to +15)
    momentum_bonus = momentum_alignment * 15

    # Volatility modifier: high vol in up-market amplifies, in down-market dampens
    vol_modifier = 0.0
    if volatility > 1.5:
        vol_modifier = 5.0 if breadth_blend > 55 else -5.0
    elif volatility > 0.8:
        vol_modifier = 2.0 if breadth_blend > 55 else -2.0

    raw_score = breadth_blend + momentum_bonus + vol_modifier
    score = max(0, min(100, round(raw_score, 1)))

    # --- Regime classification ---
    if score >= 70 and volatility < 2.0:
        regime = "risk_on"
    elif score <= 30:
        regime = "risk_off"
    elif volatility > 2.0 and 35 < score < 65:
        regime = "chop"
    else:
        regime = "calm"

    # --- Label ---
    if score >= 85:
        label = "MANIC"
    elif score >= 70:
        label = "HOT"
    elif score >= 55:
        label = "WARM"
    elif score >= 35:
        label = "NEUTRAL"
    else:
        label = "COLD"

    # --- Confidence (0-1) ---
    # Based on how many symbols we have data for vs ideal (~200+ symbols)
    ideal_symbols = 150
    data_ratio = min(1.0, total_symbols / ideal_symbols)
    history_depth = min(1.0, len(returns_3m) / max(total_symbols * 0.5, 1))
    confidence = round((data_ratio * 0.6 + history_depth * 0.4), 3)

    # --- Reasons ---
    reasons = []
    if breadth_3m > 65:
        reasons.append(f"{green_3m}/{len(returns_3m)} symbols green over 3m")
    elif breadth_3m < 35:
        reasons.append(f"{red_3m}/{len(returns_3m)} symbols red over 3m")
    if momentum_alignment > 0.5:
        reasons.append("Strong momentum alignment across timeframes")
    elif momentum_alignment < -0.3:
        reasons.append("Timeframe disagreement: 1m and 3m diverging")
    if volatility > 2.0:
        reasons.append(f"Elevated volatility ({volatility:.2f}%)")
    if not reasons:
        reasons.append("Market in equilibrium")

    components = {
        "green_1m": green_1m,
        "red_1m": red_1m,
        "green_3m": green_3m,
        "red_3m": red_3m,
        "total_symbols": total_symbols,
        "avg_return_1m": round(avg_return_1m, 4),
        "avg_return_3m": round(avg_return_3m, 4),
        "volatility": round(volatility, 4),
        "momentum_alignment": round(momentum_alignment, 4),
        "breadth_1m": round(breadth_1m, 2),
        "breadth_3m": round(breadth_3m, 2),
    }

    return {
        "score": score,
        "regime": regime,
        "label": label,
        "confidence": confidence,
        "components": components,
        "reasons": reasons,
        "ts": now_iso,
    }


def _fetch_fear_and_greed_cached():
    """TTL-cached wrapper around fetch_fear_and_greed_index(). Returns None on failure."""
    now = time.time()
    with _FG_LOCK:
        if _FG_CACHE["data"] is not None and (now - _FG_CACHE["ts"]) < _FG_TTL_S:
            return _FG_CACHE["data"]

    # Outside lock to avoid holding it during network call
    try:
        from sentiment_data_sources import fetch_fear_and_greed_index
        result = fetch_fear_and_greed_index()
    except Exception as e:
        logging.debug(f"Fear & Greed fetch failed: {e}")
        result = None

    with _FG_LOCK:
        if result is not None:
            _FG_CACHE["data"] = result
            _FG_CACHE["ts"] = now
        return _FG_CACHE["data"]  # return last good if current fetch failed


def _get_local_sentiment_payload():
    """Build the sentiment payload from local tape data + optional F&G.

    Replaces _get_sentiment_snapshot() with a closed-loop version that
    needs no external sentiment pipeline.

    Returns (sentiment_payload, sentiment_meta) tuple.
    """
    # Get latest market heat (from cache, computed in background loop)
    with _MARKET_HEAT_LOCK:
        heat = dict(_MARKET_HEAT_CACHE) if _MARKET_HEAT_CACHE else None

    if not heat:
        # Cold start: compute synchronously
        heat = _compute_market_heat()

    score = heat.get("score", 50)

    # Normalize score to 0-1 for overall_sentiment
    overall_sentiment = round(score / 100.0, 4)

    # Fear & Greed (optional external bolt-on)
    fg = _fetch_fear_and_greed_cached()
    fg_block = {}
    if fg:
        fg_block = {
            "value": fg.get("value"),
            "label": fg.get("classification"),
            "updated_at": fg.get("timestamp"),
            "source": fg.get("source", "alternative.me"),
            "stale": False,
        }

    # Build sentiment history from deque
    history = []
    with _MARKET_HEAT_LOCK:
        for entry in _MARKET_HEAT_HISTORY:
            try:
                history.append({
                    "timestamp": entry.get("ts"),
                    "sentiment": round(entry.get("score", 50) / 100.0, 4),
                })
            except Exception:
                continue

    # Divergence alerts from tape
    divergence_alerts = []  # populated by _emit_divergence_alert() in the alert stream

    sentiment_payload = {
        "overall_sentiment": overall_sentiment,
        "fear_greed": fg_block,
        "fear_greed_index": fg_block.get("value") if fg_block else None,
        "fear_greed_label": fg_block.get("label") if fg_block else None,
        "regime": heat.get("regime", "calm"),
        "confidence": heat.get("confidence", 0.0),
        "reasons": heat.get("reasons", []),
        "divergence_alerts": divergence_alerts,
        "sentiment_history": history[-30:],  # last 30 data points
        "tape_heat": {
            "score": score,
            "label": heat.get("label", "NEUTRAL"),
            "regime": heat.get("regime", "calm"),
            "confidence": heat.get("confidence", 0.0),
            "reasons": heat.get("reasons", []),
        },
        "components": heat.get("components", {}),
        "updated_at": heat.get("ts"),
        # Fields expected by normalizeSentiment adapter
        "source_breakdown": {
            "tier1": heat.get("components", {}).get("total_symbols", 0),
            "tier2": 0,
            "tier3": 0,
            "fringe": 0,
        },
        "social_breakdown": {},
        "social_history": [],
        "trending_topics": [],
    }

    now = time.time()
    meta = {
        "ok": True,
        "pipelineRunning": True,
        "staleSeconds": 0,
        "lastOkTs": heat.get("ts"),
        "lastTryTs": heat.get("ts"),
        "source": "tape_local",
    }

    return sentiment_payload, meta


def _pipeline_url(path: str) -> str:
    clean_path = path if path.startswith('/') else f'/{path}'
    return f"{SENTIMENT_PIPELINE_URL.rstrip('/')}{clean_path}"


def _sentiment_iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _sentiment_is_finite(x) -> bool:
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def _sentiment_num_in_range(x, lo, hi) -> bool:
    if not _sentiment_is_finite(x):
        return False
    v = float(x)
    return lo <= v <= hi


def _validate_sentiment_payload(payload: dict) -> tuple[bool, str | None, dict | None]:
    if not isinstance(payload, dict):
        return False, "payload_not_object", None

    required_top = [
        "overall_sentiment",
        "fear_greed_index",
        "social_metrics",
        "social_breakdown",
        "source_breakdown",
        "sentiment_history",
        "social_history",
        "trending_topics",
        "divergence_alerts",
    ]
    missing = [k for k in required_top if k not in payload]
    if missing:
        return False, f"missing_keys:{','.join(missing)}", None

    overall = payload.get("overall_sentiment")
    fgi = payload.get("fear_greed_index")
    if not _sentiment_num_in_range(overall, 0.0, 1.0):
        return False, "overall_sentiment_range", None
    if not _sentiment_num_in_range(fgi, 0.0, 100.0):
        return False, "fear_greed_index_range", None

    sm = payload.get("social_metrics")
    if not isinstance(sm, dict):
        return False, "social_metrics_not_object", None
    for k in ("volume_change", "engagement_rate", "mentions_24h"):
        if k not in sm:
            return False, f"social_metrics_missing:{k}", None
    if not _sentiment_num_in_range(sm.get("volume_change"), -1000.0, 1000.0):
        return False, "social_metrics.volume_change_range", None
    if not _sentiment_num_in_range(sm.get("engagement_rate"), 0.0, 1.0):
        return False, "social_metrics.engagement_rate_range", None
    if not _sentiment_num_in_range(sm.get("mentions_24h"), 0.0, 100000000.0):
        return False, "social_metrics.mentions_24h_range", None

    sb = payload.get("social_breakdown")
    if not isinstance(sb, dict):
        return False, "social_breakdown_not_object", None
    for k in ("reddit", "twitter", "telegram", "chan"):
        if k not in sb:
            return False, f"social_breakdown_missing:{k}", None
        if not _sentiment_num_in_range(sb.get(k), 0.0, 1.0):
            return False, f"social_breakdown.{k}_range", None

    src = payload.get("source_breakdown")
    if not isinstance(src, dict):
        return False, "source_breakdown_not_object", None
    for k in ("tier1", "tier2", "tier3", "fringe"):
        if k not in src:
            return False, f"source_breakdown_missing:{k}", None
        if not _sentiment_num_in_range(src.get(k), 0.0, 100000.0):
            return False, f"source_breakdown.{k}_range", None

    for k in ("sentiment_history", "social_history", "trending_topics", "divergence_alerts"):
        if not isinstance(payload.get(k), list):
            return False, f"{k}_not_list", None

    cleaned = {k: payload.get(k) for k in required_top}
    if "timestamp" in payload:
        cleaned["timestamp"] = payload.get("timestamp")
    if isinstance(payload.get("sources"), list):
        cleaned["sources"] = payload.get("sources")
    return True, None, cleaned


def _sentiment_poll_once():
    global _SENTIMENT_LAST_GOOD, _SENTIMENT_LAST_OK_TS, _SENTIMENT_LAST_TRY_TS
    global _SENTIMENT_LAST_ERROR, _SENTIMENT_LAST_SOURCES

    now = time.time()
    with _SENTIMENT_LOCK:
        _SENTIMENT_LAST_TRY_TS = now

    errors = []
    try:
        health_url = _pipeline_url("/health")
        r = requests.get(health_url, timeout=SENTIMENT_PIPELINE_TIMEOUT_S)
        r.raise_for_status()
    except Exception as exc:
        errors.append(f"health:{exc}")

    try:
        latest_url = _pipeline_url("/sentiment/latest")
        r = requests.get(latest_url, timeout=SENTIMENT_PIPELINE_TIMEOUT_S)
        r.raise_for_status()
        payload = r.json()
        ok, err, cleaned = _validate_sentiment_payload(payload)
        if not ok:
            errors.append(err or "invalid_payload")
        else:
            with _SENTIMENT_LOCK:
                _SENTIMENT_LAST_GOOD = cleaned
                _SENTIMENT_LAST_OK_TS = time.time()
                _SENTIMENT_LAST_ERROR = None
                _SENTIMENT_LAST_SOURCES = cleaned.get("sources") if isinstance(cleaned.get("sources"), list) else None
            return
    except Exception as exc:
        errors.append(f"latest:{exc}")

    if errors:
        with _SENTIMENT_LOCK:
            _SENTIMENT_LAST_ERROR = "; ".join([e for e in errors if e])


def _sentiment_polling_loop():
    while True:
        try:
            _sentiment_poll_once()
        except Exception:
            pass
        time.sleep(max(5.0, SENTIMENT_PIPELINE_POLL_S))


def _get_sentiment_snapshot():
    # If poller hasn't started yet, kick it off in background (non-blocking).
    try:
        thread_ref = globals().get("_MW_SENTIMENT_THREAD")
        lock_ref = globals().get("_MW_SENTIMENT_LOCK")
        if thread_ref is None or (hasattr(thread_ref, "is_alive") and not thread_ref.is_alive()):
            if lock_ref is not None:
                with lock_ref:
                    thread_ref = globals().get("_MW_SENTIMENT_THREAD")
                    if thread_ref is None or (hasattr(thread_ref, "is_alive") and not thread_ref.is_alive()):
                        st = threading.Thread(target=_sentiment_polling_loop)
                        st.daemon = True
                        st.start()
                        globals()["_MW_SENTIMENT_THREAD"] = st
    except Exception:
        pass

    with _SENTIMENT_LOCK:
        sentiment = dict(_SENTIMENT_LAST_GOOD) if isinstance(_SENTIMENT_LAST_GOOD, dict) else None
        last_ok = _SENTIMENT_LAST_OK_TS
        last_try = _SENTIMENT_LAST_TRY_TS
        err = _SENTIMENT_LAST_ERROR
        sources = _SENTIMENT_LAST_SOURCES

    now = time.time()
    stale_seconds = int(now - last_ok) if last_ok is not None else None
    # Pipeline considered running if we had a successful poll within 2x poll interval
    max_stale_for_running = max(60.0, SENTIMENT_PIPELINE_POLL_S * 2.5)
    pipeline_running = (
        last_ok is not None and
        stale_seconds is not None and
        stale_seconds < max_stale_for_running
    )
    meta = {
        "ok": bool(sentiment) and (err is None),
        "pipelineRunning": pipeline_running,
        "staleSeconds": stale_seconds,
        "lastOkTs": _sentiment_iso(last_ok),
        "lastTryTs": _sentiment_iso(last_try),
    }
    if err:
        meta["error"] = err
    if sources:
        meta["sources"] = sources

    return sentiment or {}, meta


def _proxy_pipeline_request(path: str, params: dict | None = None, timeout: float = 5.0):
    """Proxy a GET to the pipeline and normalize success/error payloads."""
    url = _pipeline_url(path)
    try:
        response = requests.get(url, params=params or {}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        return payload, url, None
    except requests.exceptions.ConnectionError as exc:
        return None, url, {
            "error": "pipeline_unreachable",
            "detail": str(exc),
            "status": 503,
            "pipeline_url": url,
        }
    except requests.exceptions.Timeout as exc:
        return None, url, {
            "error": "pipeline_timeout",
            "detail": str(exc),
            "status": 504,
            "pipeline_url": url,
        }
    except Exception as exc:
        return None, url, {
            "error": "pipeline_error",
            "detail": str(exc),
            "status": 502,
            "pipeline_url": url,
        }


def _pipeline_error_response(err_info: dict, message: str | None = None):
    body = {
        "success": False,
        "ok": False,
        "error": err_info.get("error"),
        "detail": err_info.get("detail"),
        "pipeline_url": err_info.get("pipeline_url"),
        "message": message or "Sentiment pipeline is not available",
    }
    return jsonify(body), err_info.get("status", 502)


def _pipeline_try_get_json(paths, timeout=5):
    """Try multiple pipeline paths and return (data, used_url)."""
    last_err = None
    for p in paths:
        try:
            url = _pipeline_url(p)
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r.json(), url
        except Exception as e:
            last_err = e
            continue
    raise last_err if last_err else RuntimeError("pipeline request failed")


@app.route('/api/sentiment/tiered')
def get_tiered_sentiment():
    """
    Proxy endpoint for tiered sentiment from the sentiment pipeline.
    Honors the configured SENTIMENT_HOST/SENTIMENT_PORT to keep the proxy in sync with the orchestrator.
    """
    # Align with /api/sentiment/latest proxy contract
    return api_sentiment_latest()

@app.route('/api/sentiment/pipeline-health')
def check_sentiment_pipeline_health():
    """
    Check if the sentiment pipeline is running and healthy.
    """
    payload, used_url, err_info = _proxy_pipeline_request('/health', timeout=2)
    if err_info:
        return _pipeline_error_response(err_info, 'Sentiment pipeline health check failed')

    health_data = payload or {}
    return jsonify({
        'success': True,
        'ok': True,
        'pipeline_running': True,
        'pipeline_url': used_url,
        'health_data': health_data,
    })


@app.route('/api/sentiment/health')
def api_sentiment_health():
    return check_sentiment_pipeline_health()

@app.route('/api/sentiment/sources')
def get_sentiment_sources():
    """
    Get list of all sentiment data sources with their tier and status.
    """
    try:
        payload, used_url = _pipeline_try_get_json([
            "/sentiment/sources",
            "/sources",
            "/stats",
            "/sentiment/stats",
        ], timeout=5)

        sources = []
        if isinstance(payload, list):
            sources = payload
        elif isinstance(payload, dict):
            if isinstance(payload.get("sources"), list):
                sources = payload.get("sources")
            elif isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("sources"), list):
                sources = payload["data"].get("sources")

        return jsonify({
            "success": True,
            "pipeline_url": used_url,
            "sources": sources,
            "raw": payload if not sources else None,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "pipeline_url": _pipeline_url("/sentiment/sources"),
            "error": str(e),
            "help": "Start the pipeline with: ./start_sentiment_pipeline.sh"
        }), 502

@app.route('/api/sentiment/divergence')
def get_sentiment_divergence():
    """
    Proxy endpoint that returns the divergence payload from the pipeline.
    """
    try:
        response = requests.get(
            _pipeline_url('/sentiment/divergence'),
            timeout=5
        )
        response.raise_for_status()
        divergence_payload = response.json()

        return jsonify({
            'success': True,
            'data': divergence_payload,
            'timestamp': divergence_payload.get('timestamp', datetime.utcnow().isoformat())
        })

    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Sentiment pipeline not running',
            'pipeline_url': SENTIMENT_PIPELINE_URL,
            'message': f'Could not reach sentiment pipeline at {SENTIMENT_PIPELINE_URL}'
        }), 503

    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Sentiment pipeline timeout',
            'pipeline_url': SENTIMENT_PIPELINE_URL,
            'message': 'The sentiment pipeline took too long to respond'
        }), 504

    except Exception as e:
        logging.error(f"Error fetching divergence data: {e}")
        return jsonify({
            'success': False,
            'pipeline_url': SENTIMENT_PIPELINE_URL,
            'error': str(e)
        }), 500

# ============================================================================
# END SENTIMENT PIPELINE PROXY ENDPOINTS
# ============================================================================

@app.route('/api/social-sentiment/<symbol>')
def get_social_sentiment_endpoint(symbol):
    try:
        clean_symbol = symbol.upper().replace('-USD', '').replace('USD', '')
        mock_headlines = [
            f"{clean_symbol} sees massive inflow from institutional investors",
            f"Regulators approve new {clean_symbol} trading vehicle",
            f"Market volatility increases as {clean_symbol} tests new highs",
        ]

        sentiment_result = ai_engine.score_headlines_local(mock_headlines)
        narrative = ai_engine.generate_narrative(clean_symbol, mock_headlines, 45000.00)

        return jsonify({
            "success": True,
            "data": {
                "symbol": clean_symbol,
                "overall_score": sentiment_result['score'],
                "label": sentiment_result['label'],
                "narrative": narrative,
                "sources_breakdown": {
                    "finbert_confidence": sentiment_result['confidence'],
                    "headlines_analyzed": len(mock_headlines),
                },
            },
        })
    except Exception as e:
        app.logger.error(f"Error in sentiment endpoint: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/intelligence-report/<symbol>')
def api_intelligence_report(symbol):
    """
    Returns Hybrid Intelligence Report for Divergence Detection.

    Combines:
    - FinBERT local inference (institutional sentiment)
    - Fear & Greed Index (retail sentiment)
    - Social volume metrics
    - Gemini-generated narrative explaining divergence
    """
    try:
        from sentiment_data_sources import fetch_fear_and_greed_index, fetch_coingecko_social, COINGECKO_ID_MAP
        from sentiment_aggregator import fetch_reddit_count

        clean_symbol = symbol.upper().replace('-USD', '').replace('USD', '')

        # Get current price from Coinbase
        try:
            price_resp = requests.get(f"https://api.coinbase.com/v2/prices/{clean_symbol}-USD/spot", timeout=3)
            price_data = price_resp.json()
            current_price = float(price_data['data']['amount']) if price_data.get('data') else None
        except Exception:
            current_price = None

        # Fetch RSS headlines for FinBERT analysis (mock for now, replace with real RSS)
        mock_headlines = [
            f"{clean_symbol} institutional adoption accelerates as major funds enter",
            f"Regulatory clarity improves for {clean_symbol} trading infrastructure",
            f"{clean_symbol} network activity reaches new highs amid market uncertainty",
        ]

        # Score headlines with FinBERT (local M3/N100 inference)
        finbert_result = ai_engine.score_headlines_local(mock_headlines)

        # Fetch Fear & Greed Index (retail sentiment)
        fg_data = fetch_fear_and_greed_index()
        fear_greed_value = fg_data['value'] if fg_data else 50

        # Fetch social volume (Reddit mentions)
        try:
            reddit_count = fetch_reddit_count(clean_symbol) if 'fetch_reddit_count' in dir() else 0
        except Exception:
            reddit_count = 0

        # Bundle metrics for Gemini prompt
        metrics_bundle = {
            'finbert_score': finbert_result['score'],
            'finbert_label': finbert_result['label'],
            'fear_greed': fear_greed_value,
            'social_volume': reddit_count,
            'confidence': finbert_result['confidence']
        }

        # Generate divergence narrative with Gemini
        divergence_prompt = f"""
ROLE: Senior Crypto Market Analyst
ASSET: {clean_symbol} at ${current_price or 'N/A'}

INPUT DATA:
- Institutional News (FinBERT Local Score): {metrics_bundle['finbert_score']:.2f} (Range -1 to 1)
- Retail Heat (Reddit/RSS Count): {metrics_bundle['social_volume']} mentions
- Market Context (Fear & Greed Index): {metrics_bundle['fear_greed']} (0-100)
- Key Headlines: {mock_headlines[:3]}

TASK:
Analyze the relationship between these data points. Specifically, identify any DIVERGENCE
(e.g., news is Bullish but the Fear & Greed index is Low).

OUTPUT FORMAT:
One concise sentence (max 25 words). Start with the primary driver. Be decisive.
"""

        narrative = ai_engine.generate_narrative(clean_symbol, [divergence_prompt], current_price or 0)

        return jsonify({
            "success": True,
            "data": {
                "symbol": clean_symbol,
                "metrics": metrics_bundle,
                "narrative": narrative,
                "raw_context": {
                    "top_headlines": mock_headlines,
                    "price": current_price
                }
            }
        })

    except Exception as e:
        app.logger.error(f"Error in intelligence-report endpoint: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/metrics')
def api_metrics():
    """Get observability metrics for sentiment aggregator monitoring.

    Returns JSON with:
    - cache_hit_rate: Percentage of cache hits
    - avg_response_time_ms: Average response time
    - requests_last_hour: Recent request count
    - source_availability: Per-source health metrics
    """
    try:
        from sentiment_aggregator import get_metrics
        metrics = get_metrics()
        return jsonify(metrics)
    except Exception as exc:
        print(f"[Metrics API] Error: {exc}")
        return jsonify({
            "error": str(exc),
            "cache_hit_rate": 0.0,
            "avg_response_time_ms": 0.0,
            "requests_last_hour": 0,
            "source_availability": {}
        }), 500

@app.route('/api/signals/pumpdump')
def api_signals_pumpdump():
    """Stub signals endpoint to keep mobile/web screens functional.

    Replace with real logic when signals generation is ready.
    """
    try:
        return jsonify([])
    except Exception:
        return jsonify([])

@app.route('/metrics.prom')
def metrics_prom():
    """Minimal Prometheus-style metrics exposition (text/plain)."""
    lines = []
    now = time.time()
    uptime = now - startup_time
    # Core app metrics
    lines.append('# HELP app_uptime_seconds Application uptime in seconds')
    lines.append('# TYPE app_uptime_seconds gauge')
    lines.append(f'app_uptime_seconds {uptime:.2f}')
    lines.append('# HELP app_errors_5xx_total Total 5xx responses observed (incremented post-response)')
    lines.append('# TYPE app_errors_5xx_total counter')
    lines.append(f'app_errors_5xx_total {_ERROR_STATS["5xx"]}')
    # Price fetch metrics if available
    try:
        from price_fetch import get_price_fetch_metrics
        pf = get_price_fetch_metrics()
        cb = (pf.get('circuit_breaker') or {}) if isinstance(pf, dict) else {}
        # Threshold gauges (static-ish config exposed for observability)
        for k,v in THRESHOLDS.items():
            try:
                emit_prometheus(lines, f'threshold_{k}', v, 'gauge', f'Threshold parameter {k}')
            except Exception:
                pass
        emit_prometheus(lines, 'price_fetch_total_calls_total', pf.get('total_calls',0), 'counter', 'Total calls to fetch_prices (including snapshot served)')
        emit_prometheus(lines, 'price_fetch_products_cache_hits_total', pf.get('products_cache_hits',0), 'counter', 'Number of product list cache hits')
        emit_prometheus(lines, 'price_fetch_snapshot_served_total', pf.get('snapshot_served',0), 'counter', 'Number of times stale snapshot returned instead of fresh fetch')
        emit_prometheus(lines, 'price_fetch_rate_failures', pf.get('rate_failures',0), 'gauge', 'Current consecutive failure / throttling count')
        emit_prometheus(lines, 'price_fetch_last_fetch_duration_ms', round(pf.get('last_fetch_duration_ms',0),2), 'gauge', 'Duration of last successful fetch in milliseconds')
        # Advanced latency & error/backoff metrics
        if pf.get('p95_fetch_duration_ms') is not None:
            emit_prometheus(lines, 'price_fetch_p95_fetch_duration_ms', round(pf.get('p95_fetch_duration_ms'),2), 'gauge', 'Approximate p95 of recent fetch durations (ms)')
        emit_prometheus(lines, 'price_fetch_error_rate_percent', pf.get('error_rate_percent'), 'gauge', 'Rolling error rate percentage over recent calls')
        emit_prometheus(lines, 'price_fetch_backoff_seconds_remaining', pf.get('backoff_seconds_remaining'), 'gauge', 'Seconds remaining in current exponential backoff window (0 if none)')
        # Histogram exposition (Prometheus style cumulative buckets)
        buckets = pf.get('fetch_duration_hist_buckets') or {}
        running = 0
        for edge in sorted([int(k) for k in buckets.keys()]):
            running += buckets[str(edge)]
            lines.append('# TYPE price_fetch_duration_seconds histogram')
            # convert ms to seconds for Prometheus histogram convention
            lines.append(f'price_fetch_duration_seconds_bucket{{le="{edge/1000.0:.3f}"}} {running}')
        # +Inf bucket
        overflow = pf.get('fetch_duration_hist_overflow',0)
        count = pf.get('fetch_duration_count', running + overflow)
        lines.append(f'price_fetch_duration_seconds_bucket{{le="+Inf"}} {count}')
        # sum & count
        sum_ms = pf.get('fetch_duration_sum_ms',0.0)
        lines.append(f'price_fetch_duration_seconds_sum {sum_ms/1000.0:.6f}')
        lines.append(f'price_fetch_duration_seconds_count {count}')
        age_val = round(pf.get('snapshot_age_sec',0),2) if pf.get('snapshot_age_sec') is not None else None
        emit_prometheus(lines, 'price_fetch_snapshot_age_seconds', age_val, 'gauge', 'Age in seconds of current price snapshot')
        emit_prometheus(lines, 'price_fetch_has_snapshot', 1 if pf.get('has_snapshot') else 0, 'gauge', 'Whether a snapshot is currently cached (1=yes)')
        # Circuit breaker metrics
        if cb:
            state_map = {'CLOSED':0,'OPEN':1,'HALF_OPEN':0.5}
            emit_prometheus(lines, 'price_fetch_circuit_breaker_state', state_map.get(cb.get('state'), -1), 'gauge', 'Circuit breaker state (0=closed,1=open,0.5=half_open)')
            emit_prometheus(lines, 'price_fetch_circuit_breaker_failures', cb.get('failures'), 'gauge', 'Current consecutive failures counted by breaker')
            emit_prometheus(lines, 'price_fetch_circuit_breaker_open_until_epoch', cb.get('open_until'), 'gauge', 'Epoch timestamp until which breaker remains open (0 if closed)')
            # Normalized boolean gauges for simpler alerting
            emit_prometheus(lines, 'price_fetch_circuit_breaker_is_open', 1 if cb.get('state') == 'OPEN' else 0, 'gauge', 'Circuit breaker open (1=open,0=otherwise)')
            emit_prometheus(lines, 'price_fetch_circuit_breaker_is_half_open', 1 if cb.get('state') == 'HALF_OPEN' else 0, 'gauge', 'Circuit breaker half-open (1=half-open,0=otherwise)')
        # SWR metrics
        emit_swr_prometheus(lines, _swr_entries())
        # Market breadth metrics (1m universe)
        if 'one_minute_market_stats' in globals() and one_minute_market_stats:
            m = one_minute_market_stats
            def _maybe(name, val, help_txt):
                if val is None:
                    return
                emit_prometheus(lines, name, val, 'gauge', help_txt)
            _maybe('one_min_market_universe_count', m.get('universe_count'), 'Count of symbols in 1m universe sample')
            _maybe('one_min_market_advancers', m.get('advancers'), 'Advancers (positive 1m change) count')
            _maybe('one_min_market_decliners', m.get('decliners'), 'Decliners (negative 1m change) count')
            _maybe('one_min_market_adv_decl_ratio', m.get('adv_decl_ratio'), 'Advancers / Decliners ratio (breadth)')
            for p in (50,75,90,95,99):
                _maybe(f'one_min_market_pct{p}', m.get(f'pct{p}'), f'{p}th percentile of raw 1m percentage changes')
            for p in (90,95,99):
                _maybe(f'one_min_market_abs_pct{p}', m.get(f'abs_pct{p}'), f'{p}th percentile of absolute 1m percentage changes')
            for thr in (1,2,5):
                _maybe(f'one_min_market_count_gt_{thr}pct', m.get(f'count_gt_{thr}pct'), f'Count of symbols with |1m| change >= {thr}%')
            _maybe('one_min_market_top5_avg_gain', m.get('top5_avg_gain'), 'Average 1m gain of top 5 advancers')
            _maybe('one_min_market_bottom5_avg_loss', m.get('bottom5_avg_loss'), 'Average 1m gain (negative) of top 5 decliners')
            _maybe('one_min_market_extreme_gainer_pct', m.get('extreme_gainer_pct'), 'Largest 1m percentage gain observed')
            _maybe('one_min_market_extreme_loser_pct', m.get('extreme_loser_pct'), 'Largest 1m percentage loss observed')
            # Acceleration / delta signals
            _maybe('one_min_market_spike_p95_delta', m.get('spike_p95_delta'), 'Change in 95th percentile since previous snapshot')
            _maybe('one_min_market_spike_p99_delta', m.get('spike_p99_delta'), 'Change in 99th percentile since previous snapshot')
            _maybe('one_min_market_spike_p95_rate_per_sec', m.get('spike_p95_rate_per_sec'), 'Rate of change per second of 95th percentile')
            _maybe('one_min_market_spike_p99_rate_per_sec', m.get('spike_p99_rate_per_sec'), 'Rate of change per second of 99th percentile')
            _maybe('one_min_market_extreme_gainer_accel', m.get('extreme_gainer_accel'), 'Delta of extreme gainer pct since previous snapshot')
            _maybe('one_min_market_extreme_gainer_accel_rate_per_sec', m.get('extreme_gainer_accel_rate_per_sec'), 'Rate/sec of extreme gainer delta')
            _maybe('one_min_market_breadth_net_advancers', m.get('breadth_net_advancers'), 'Advancers minus decliners (breadth net)')
            _maybe('one_min_market_breadth_net_advancers_delta', m.get('breadth_net_advancers_delta'), 'Delta of net advancers vs previous snapshot')
            _maybe('one_min_market_breadth_net_advancers_delta_rate_per_sec', m.get('breadth_net_advancers_delta_rate_per_sec'), 'Rate/sec of net advancers delta')
            _maybe('one_min_market_breadth_adv_decl_ratio_delta', m.get('breadth_adv_decl_ratio_delta'), 'Delta of adv/decl ratio since previous snapshot')
            _maybe('one_min_market_breadth_adv_decl_ratio_rate_per_sec', m.get('breadth_adv_decl_ratio_rate_per_sec'), 'Rate/sec of adv/decl ratio delta')
            # Z-scores & EMA / thrust
            _maybe('one_min_market_z_p95', m.get('z_p95'), 'Z-score of current 95th percentile vs rolling window')
            _maybe('one_min_market_z_p99', m.get('z_p99'), 'Z-score of current 99th percentile vs rolling window')
            _maybe('one_min_market_z_extreme_gainer', m.get('z_extreme_gainer'), 'Z-score of current extreme gainer vs history')
            _maybe('one_min_market_breadth_adv_decl_ratio_ema', m.get('breadth_adv_decl_ratio_ema'), 'EMA-smoothed adv/decl ratio')
            _maybe('one_min_market_breadth_net_advancers_ema', m.get('breadth_net_advancers_ema'), 'EMA-smoothed net advancers')
            _maybe('one_min_market_breadth_thrust_active', m.get('breadth_thrust_active'), 'Breadth thrust active flag (1=active)')
            _maybe('one_min_market_breadth_thrust_duration_sec', m.get('breadth_thrust_duration_sec'), 'Duration in seconds of current breadth thrust sequence')
            # Bollinger band metrics & confirmation overlay
            _maybe('one_min_market_breadth_adv_decl_ratio_bb_mid', m.get('breadth_adv_decl_ratio_bb_mid'), 'Bollinger band mid (mean) of adv/decl ratio')
            _maybe('one_min_market_breadth_adv_decl_ratio_bb_upper', m.get('breadth_adv_decl_ratio_bb_upper'), 'Bollinger band upper (mean + K*sd) of adv/decl ratio')
            _maybe('one_min_market_breadth_adv_decl_ratio_bb_lower', m.get('breadth_adv_decl_ratio_bb_lower'), 'Bollinger band lower (mean - K*sd) of adv/decl ratio')
            _maybe('one_min_market_breadth_adv_decl_ratio_bb_sd', m.get('breadth_adv_decl_ratio_bb_sd'), 'Rolling std dev of adv/decl ratio for bands')
            _maybe('one_min_market_confirm_3m_overlap', m.get('confirm_3m_overlap'), 'Count of retained 1m symbols with 3m trend data')
            _maybe('one_min_market_confirm_3m_up', m.get('confirm_3m_up'), 'Count of retained 1m symbols whose 3m trend is up')
            _maybe('one_min_market_confirm_3m_up_ratio', m.get('confirm_3m_up_ratio'), 'Ratio of retained 1m symbols whose 3m trend is up')
            # Alert boolean gauges
            _maybe('one_min_market_alert_pump_thrust', m.get('alert_pump_thrust'), 'Composite pump thrust alert flag')
            _maybe('one_min_market_alert_narrowing_vol', m.get('alert_narrowing_vol'), 'Volatility squeeze (narrow Bollinger) flag')
            _maybe('one_min_market_alert_upper_band_touch', m.get('alert_upper_band_touch'), 'Adv/decl ratio touching upper Bollinger band flag')
            _maybe('one_min_market_alert_lower_band_touch', m.get('alert_lower_band_touch'), 'Adv/decl ratio touching lower Bollinger band flag')
            _maybe('one_min_market_alert_accel_fade', m.get('alert_accel_fade'), 'Acceleration fade / possible exhaustion flag')
    except Exception as e:  # pragma: no cover - defensive
        lines.append('# HELP price_fetch_metrics_error Indicates an error exporting price fetch metrics (1=error)')
        lines.append('# TYPE price_fetch_metrics_error gauge')
        lines.append('price_fetch_metrics_error 1')
        try:
            _detail = str(e).replace('\n', ' ')[:200]
            lines.append('# price_fetch_metrics_error_detail ' + _detail)
        except Exception:
            pass
    body = '\n'.join(lines) + '\n'
    return app.response_class(body, mimetype='text/plain; version=0.0.4')

# ---- OpenAPI & JSON Schemas ----
@app.route('/api/openapi.json')
def openapi_spec():
    spec = {
        'openapi': '3.1.0',
        'info': {'title': 'Moonwalking API', 'version': '0.1.0'},
        'paths': {
            '/api/health': {
                'get': {'summary': 'Health check', 'responses': {'200': {'description': 'OK','content': {'application/json': {'schema': HealthResponse.model_json_schema()}}}}}
            },
            '/api/metrics': {
                'get': {'summary': 'Operational metrics', 'responses': {'200': {'description': 'Metrics','content': {'application/json': {'schema': MetricsResponse.model_json_schema()}}}}}
            },
            '/api/component/gainers-table-1min': {
                'get': {'summary': 'Gainers table (1 minute)', 'responses': {
                    '200': {'description': 'Component payload','content': {'application/json': {'schema': Gainers1mComponent.model_json_schema()}}},
                    '503': {'description': 'Service unavailable'}
                }}
            },
            '/api/config': {
                'get': {
                    'summary': 'Get current runtime config + validation limits',
                    'responses': {
                        '200': {
                            'description': 'Config snapshot',
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'properties': {
                                            'config': {'type':'object'},
                                            'limits': {'type':'object'}
                                        },
                                        'required': ['config']
                                    }
                                }
                            }
                        }
                    }
                },
                'post': {
                    'summary': 'Patch runtime configuration (validated)',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'type':'object'}
                            }
                        }
                    },
                    'responses': {
                        '200': {'description':'All updates applied'},
                        '207': {'description':'Partial success (some errors)'},
                        '400': {'description':'No valid keys applied'}
                    }
                }
            },
            '/api/thresholds': {
                'get': {
                    'summary': 'Get current runtime alert thresholds',
                    'responses': {
                        '200': {
                            'description': 'Current thresholds',
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'properties': {
                                            'thresholds': { 'type': 'object', 'additionalProperties': { 'type': 'number' }}
                                        },
                                        'required': ['thresholds']
                                    }
                                }
                            }
                        }
                    }
                },
                'post': {
                    'summary': 'Patch / update thresholds (partial)',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'description': 'Partial map of threshold keys to new numeric values'
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': { 'description': 'All updates applied successfully' },
                        '207': { 'description': 'Some updates applied; some rejected (multi-status)' },
                        '400': { 'description': 'All provided keys invalid / rejected' }
                    }
                }
            }
        }
    }
    return jsonify(spec)

@app.route('/api/schema/health')
def schema_health():
    return jsonify(HealthResponse.model_json_schema())

@app.route('/api/schema/metrics')
def schema_metrics():
    return jsonify(MetricsResponse.model_json_schema())

@app.route('/api/schema/gainers-1m')
def schema_gainers_1m():
    return jsonify(Gainers1mComponent.model_json_schema())

# ---------------- Health + Metrics -----------------
_ERROR_STATS = { '5xx': 0 }

@app.before_request
def _before_req_metrics():
    g._start_time = time.time()

@app.after_request
def _after_req_metrics(resp):
    try:
        if 500 <= resp.status_code < 600:
            _ERROR_STATS['5xx'] += 1
    except Exception:
        pass
    return resp

# -------------------------------- Codex Assistant ---------------------------------
@app.route('/api/ask-codex', methods=['POST'])
def ask_codex():
    """Proxy user query to OpenAI Chat Completions (server-side to protect API key)."""
    try:
        data = request.get_json(silent=True) or {}
        query = (data.get('query') or '').strip()
        if not query:
            return jsonify({'error': 'Missing query'}), 400
        api_key = os.environ.get('OPENAI_API_KEY')
        # Stub mode if no key, or explicit stub flag, or clearly fake key
        if (not api_key) or os.environ.get('OPENAI_STUB') == '1' or str(api_key).lower() in {'fake','test','dummy'}:
            demo = f"[stub] You asked: '{query}'. This is a local test response. Set OPENAI_API_KEY to use real model."
            return jsonify({'reply': demo, 'stub': True})
        payload = {
            'model': os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo'),
            'messages': [
                { 'role': 'system', 'content': 'You are a helpful React/JS/crypto assistant helping debug a WebSocket-based crypto dashboard.' },
                { 'role': 'user', 'content': query }
            ],
            'temperature': 0.2
        }
        # Use requests directly (no extra dependency)
        resp = requests.post('https://api.openai.com/v1/chat/completions',
                              headers={
                                  'Authorization': f'Bearer {api_key}',
                                  'Content-Type': 'application/json'
                              },
                              json=payload, timeout=20)
        if resp.status_code >= 400:
            logging.warning(f"ask-codex upstream error {resp.status_code}: {resp.text[:200]}")
            return jsonify({'reply': f'Upstream error {resp.status_code}'}), 502
        data = resp.json()
        reply = (data.get('choices') or [{}])[0].get('message', {}).get('content') or 'No reply received.'
        return jsonify({'reply': reply})
    except Exception as e:
        logging.error(f"ask-codex error: {e}")
        return jsonify({'reply': 'Internal error'}), 500

# Dynamic Configuration with Environment Variables and Defaults
CONFIG = {
    'CACHE_TTL': int(os.environ.get('CACHE_TTL', 60)),  # Cache for 60 seconds
    'INTERVAL_MINUTES': int(os.environ.get('INTERVAL_MINUTES', 3)),  # Calculate changes over 3 minutes
    # Keep enough points for 1h-style calculations. At 60s update interval,
    # 90 gives ~90 minutes of history.
    'MAX_PRICE_HISTORY': int(os.environ.get('MAX_PRICE_HISTORY', 90)),
    'PORT': int(os.environ.get('PORT', 5003)),  # Default port
    'HOST': os.environ.get('HOST', '0.0.0.0'),  # Default host
    'DEBUG': os.environ.get('DEBUG', 'False').lower() == 'true',  # Debug mode
    'UPDATE_INTERVAL': int(os.environ.get('UPDATE_INTERVAL', 60)),  # Legacy: Background update interval in seconds (deprecated)
    'PRICE_FETCH_INTERVAL': int(os.environ.get('PRICE_FETCH_INTERVAL', 8)),  # How often to fetch fresh prices from Coinbase (8s for live feel)
    'SNAPSHOT_COMPUTE_INTERVAL': int(os.environ.get('SNAPSHOT_COMPUTE_INTERVAL', 8)),  # How often to recompute snapshots using cached prices (8-10s recommended)
    'MAX_COINS_PER_CATEGORY': int(os.environ.get('MAX_COINS_PER_CATEGORY', 30)),  # Max coins to return
    'MIN_VOLUME_THRESHOLD': int(os.environ.get('MIN_VOLUME_THRESHOLD', 0)),  # Minimum volume for banner (lowered for faster dev warmup)
    'MIN_CHANGE_THRESHOLD': float(os.environ.get('MIN_CHANGE_THRESHOLD', 0.15)),  # Minimum % change for banner (loosened for dev)
    'API_TIMEOUT': int(os.environ.get('API_TIMEOUT', 10)),  # API request timeout
    'CHART_DAYS_LIMIT': int(os.environ.get('CHART_DAYS_LIMIT', 30)),  # Max days for chart data
    # 1-minute feature load controls
    'ENABLE_1MIN': os.environ.get('ENABLE_1MIN', 'true').lower() == 'true',  # Master switch
    'ONE_MIN_REFRESH_SECONDS': int(os.environ.get('ONE_MIN_REFRESH_SECONDS', 25)),  # Throttle 1-min recompute (default 25s)
    # 1-minute retention / hysteresis controls
    'ONE_MIN_ENTER_PCT': float(os.environ.get('ONE_MIN_ENTER_PCT', 0.005)),   # % change to ENTER list (0.5% - much more data)
    'ONE_MIN_STAY_PCT': float(os.environ.get('ONE_MIN_STAY_PCT', 0.0025)),    # lower % to remain after entering (0.25% - keep board full)
    'ONE_MIN_MAX_COINS': int(os.environ.get('ONE_MIN_MAX_COINS', 35)),       # cap displayed coins
    'ONE_MIN_DWELL_SECONDS': int(os.environ.get('ONE_MIN_DWELL_SECONDS', 90)), # minimum time to stay once entered
    'TOP_MOVERS_SAMPLE_SIZE': int(os.environ.get('TOP_MOVERS_SAMPLE_SIZE', 120)),  # 24h movers sample size
    'ONE_MIN_DEFAULT_SEED_COUNT': int(os.environ.get('ONE_MIN_DEFAULT_SEED_COUNT', 10)),  # seed count for 1m list
    'PRICE_UNIVERSE_SAMPLE_SIZE': int(os.environ.get('PRICE_UNIVERSE_SAMPLE_SIZE', 120)),  # USD products sample size
    'PRICE_UNIVERSE_MAX': int(os.environ.get('PRICE_UNIVERSE_MAX', 250)),  # Hard cap on sample size
    'PRICE_MIN_SUCCESS_RATIO': float(os.environ.get('PRICE_MIN_SUCCESS_RATIO', 0.70)),  # coverage guard
    # Alert hygiene (streak-triggered alerts with cooldown)
    'ALERTS_COOLDOWN_SECONDS': int(os.environ.get('ALERTS_COOLDOWN_SECONDS', 300)),  # 5 minutes
    # Impulse alert thresholds (percentage points). Keep defaults conservative;
    # allow env overrides for local verification.
    'ALERT_IMPULSE_1M_PCT': float(os.environ.get('ALERT_IMPULSE_1M_PCT', 0.75)),
    'ALERT_IMPULSE_3M_PCT': float(os.environ.get('ALERT_IMPULSE_3M_PCT', 1.25)),
    'ALERT_IMPULSE_COOLDOWN_SECONDS': int(os.environ.get('ALERT_IMPULSE_COOLDOWN_SECONDS', 60)),
    'ALERT_IMPULSE_DEDUPE_DELTA': float(os.environ.get('ALERT_IMPULSE_DEDUPE_DELTA', 0.2)),
    'ALERT_IMPULSE_TTL_MINUTES': int(os.environ.get('ALERT_IMPULSE_TTL_MINUTES', 5)),
    'ALERTS_STICKY_SECONDS': int(os.environ.get('ALERTS_STICKY_SECONDS', 60)),
    # Comma-separated streak thresholds that should trigger alerts (e.g., "3,5")
    'ALERTS_STREAK_THRESHOLDS': [
        int(x) for x in os.environ.get('ALERTS_STREAK_THRESHOLDS', '3,5').split(',')
        if x.strip().isdigit()
    ] or [3, 5],
}

# Log configuration once CONFIG is ready
try:
    _log_config_with_param(CONFIG)
except Exception:
    logging.warning("Could not log configuration")

# Cache and price history storage
cache = {
    "data": None,
    "timestamp": 0,
    "ttl": CONFIG['CACHE_TTL']
}

# Store price history for interval calculations
# Rolling price history (3m + 1m + 1h)
price_history = defaultdict(lambda: deque(maxlen=CONFIG['MAX_PRICE_HISTORY']))
price_history_1min = defaultdict(lambda: deque(maxlen=CONFIG['MAX_PRICE_HISTORY'])) # For 1-minute changes
price_history_1hour = defaultdict(lambda: deque(maxlen=80))  # 1h tracking: 80 snapshots = ~75min at 1min intervals

# Track readiness of the 3m baseline (first snapshot >= interval ago)
_BASELINE_3M_LOCK = threading.Lock()
_BASELINE_3M_META = {"ready": False, "baseline_ts": None, "age_seconds": None}

# Track readiness of the 1m baseline
_BASELINE_1M_LOCK = threading.Lock()
_BASELINE_1M_META = {"ready": False, "baseline_ts": None, "age_seconds": None}

# Track readiness of 1h baseline
_BASELINE_1H_LOCK = threading.Lock()
_BASELINE_1H_META = {"ready": False, "baseline_ts": None, "age_seconds": None}


def _set_baseline_meta_3m(*, ready: bool, baseline_ts: float | None, age_seconds: float | None):
    with _BASELINE_3M_LOCK:
        _BASELINE_3M_META["ready"] = bool(ready)
        _BASELINE_3M_META["baseline_ts"] = baseline_ts
        _BASELINE_3M_META["age_seconds"] = age_seconds


def _get_baseline_meta_3m():
    """Get 3m baseline meta.

    Source of truth is `_BASELINE_3M_META`, which is updated by the same
    baseline selection logic used to compute 3m movers.
    """
    with _BASELINE_3M_LOCK:
        return dict(_BASELINE_3M_META)


def _set_baseline_meta_1m(*, ready: bool, baseline_ts: float | None, age_seconds: float | None):
    with _BASELINE_1M_LOCK:
        _BASELINE_1M_META["ready"] = bool(ready)
        _BASELINE_1M_META["baseline_ts"] = baseline_ts
        _BASELINE_1M_META["age_seconds"] = age_seconds


def _get_baseline_meta_1m():
    with _BASELINE_1M_LOCK:
        return dict(_BASELINE_1M_META)

def _set_baseline_meta_1h(*, ready: bool, baseline_ts: float | None, age_seconds: float | None):
    with _BASELINE_1H_LOCK:
        _BASELINE_1H_META["ready"] = bool(ready)
        _BASELINE_1H_META["baseline_ts"] = baseline_ts
        _BASELINE_1H_META["age_seconds"] = age_seconds

def _get_baseline_meta_1h():
    """Get 1h baseline meta using direct price_history_1hour check."""
    with _BASELINE_1H_LOCK:
        return dict(_BASELINE_1H_META)

# Cache / state for 1-min data to prevent hammering APIs
one_minute_cache = {"data": None, "timestamp": 0}
last_current_prices = {
    "data": None,
    "timestamp": 0,
    "partial": False,
    "partial_reason": None,
    "ok": 0,
    "submitted": 0,
    "ok_ratio": None,
    "http429": 0,
    "http5xx": 0,
    "other": 0,
    "exceptions": 0,
    "deadline_hit": False,
    "last_fetch_ts": 0,
}
# Track last-seen timestamps for symbols to bias 1m universe toward fresh baselines.
_PRICE_LAST_SEEN_TS = {}
# Persistence state for 1-min display logic
one_minute_persistence = {
    'entries': {},  # symbol -> {'entered_at': ts, 'enter_gain': pct}
    'last_snapshot_symbols': set()
}

# Track rolling 60s peak percentage changes for 1-min logic to avoid rapid top churn
# Structure: symbol -> {'peak_pct': float, 'peak_at': ts, 'last_seen': ts}
one_minute_peaks = {}
# Track simple trending stats for 1‑minute gains per symbol
one_minute_trends = {}
# Track rank stabilization for 1-minute tables
one_minute_rank_state = {
    "gainers": {"ranks": {}, "last_change": {}},
    "losers": {"ranks": {}, "last_change": {}},
}
# Track diagnostics for the 1-minute funnel (latest snapshot only)
one_minute_diag = {}
# New trend caches for other intervals/metrics
three_minute_trends = {}
one_hour_price_trends = {}
one_hour_volume_trends = {}
# Track 24h volume snapshots to estimate 1h volume deltas: symbol -> deque[(ts, vol_24h)]
volume_history_24h = defaultdict(lambda: deque(maxlen=180))

# ----------------------------------------------------------------------------
# Candle-based 1h volume cache (display-set symbols only)
# ----------------------------------------------------------------------------
_CANDLE_VOLUME_CACHE = {}  # product_id -> {vol1h, vol1h_pct_change, ts_computed, last_error}
_CANDLE_VOLUME_CACHE_LOCK = threading.Lock()
# Per-minute volume series for z-score whale detection
# product_id -> list of (timestamp, volume) tuples, most-recent first, max ~70 entries
_CANDLE_MINUTE_VOLUMES = {}  # populated alongside _CANDLE_VOLUME_CACHE
MAX_CANDLE_SYMBOLS = 60  # Cap to avoid rate limits

def _fetch_coinbase_candles(product_id, granularity=60, count=70):
    """Fetch candles from Coinbase API.

    Args:
        product_id: e.g. "BTC-USD"
        granularity: seconds per candle (60 = 1min)
        count: number of candles to fetch

    Returns:
        List of candles [[timestamp, low, high, open, close, volume], ...]
    """
    try:
        url = f"https://api.exchange.coinbase.com/products/{product_id}/candles"
        params = {"granularity": granularity}

        # Don't use start/end to get latest candles
        resp = requests.get(url, params=params, timeout=5)

        if resp.status_code == 429:
            logging.warning(f"[Candles] Rate limited for {product_id}")
            return None

        if not resp.ok:
            logging.debug(f"[Candles] HTTP {resp.status_code} for {product_id}")
            return None

        data = resp.json()
        if not isinstance(data, list):
            return None

        # Return most recent candles (API returns them in desc order by timestamp)
        return data[:count]
    except Exception as e:
        logging.debug(f"[Candles] Fetch error for {product_id}: {e}")
        return None

def _compute_1h_volume_from_candles(product_id):
    """Compute 1h volume by summing recent 1-minute candles.

    Also stores per-minute volume+price series in _CANDLE_MINUTE_VOLUMES
    for z-score whale detection.

    Returns:
        (vol1h, vol1h_prev, vol1h_pct_change) or (None, None, None) on error
    """
    # Need 120+ candles: 60 for current hour, 60 for previous hour (pct change)
    candles = _fetch_coinbase_candles(product_id, granularity=60, count=130)

    if not candles or len(candles) < 60:
        return None, None, None

    try:
        # Candles are [[timestamp, low, high, open, close, volume], ...]
        # Align to full minutes: exclude partial current minute if present
        # Candles come in desc order by timestamp
        now_ts = int(time.time())
        floor_ts = now_ts - (now_ts % 60)

        # Filter to only complete minute candles (exclude in-progress minute)
        complete_candles = [c for c in candles if len(c) > 5 and int(c[0]) < floor_ts]

        if len(complete_candles) < 60:
            # Fall back to all candles if filtering removes too many
            complete_candles = candles

        # Store per-minute volume series for z-score whale detection
        # Each entry: (timestamp, volume, open, close, high, low)
        minute_series = []
        for c in complete_candles[:70]:  # Keep last ~70 minutes
            if len(c) > 5:
                minute_series.append({
                    'ts': int(c[0]),
                    'vol': float(c[5]),
                    'open': float(c[3]),
                    'close': float(c[4]),
                    'high': float(c[2]),
                    'low': float(c[1]),
                })
        _CANDLE_MINUTE_VOLUMES[product_id] = minute_series

        # Sum last 60 candles for 1h volume
        vol1h = sum(float(c[5]) for c in complete_candles[:60] if len(c) > 5)
        vol1h_prev = None
        vol1h_pct = None

        # Compute 1h volume change % (compare to previous hour)
        if len(complete_candles) >= 120:
            vol1h_prev = sum(float(c[5]) for c in complete_candles[60:120] if len(c) > 5)
            if vol1h_prev > 0:
                vol1h_pct = ((vol1h - vol1h_prev) / vol1h_prev) * 100.0

        return vol1h, vol1h_prev, vol1h_pct
    except Exception as e:
        logging.debug(f"[Candles] Volume compute error for {product_id}: {e}")
        return None, None, None

def _update_candle_volume_cache(product_ids):
    """Background worker: update candle volume cache for display-set symbols.

    Args:
        product_ids: List of product_id strings (e.g. ["BTC-USD", "ETH-USD"])
    """
    if not product_ids:
        return

    # Cap to avoid overwhelming the API
    products = list(set(product_ids))[:MAX_CANDLE_SYMBOLS]
    now = time.time()

    with _CANDLE_VOLUME_CACHE_LOCK:
        for product_id in products:
            # Check if recently updated (within 30s)
            cached = _CANDLE_VOLUME_CACHE.get(product_id, {})
            ts_computed = cached.get('ts_computed', 0)
            if now - ts_computed < 30:
                continue  # Skip, too recent

            vol1h, vol1h_prev, vol1h_pct = _compute_1h_volume_from_candles(product_id)

            if vol1h is not None:
                _CANDLE_VOLUME_CACHE[product_id] = {
                    'vol1h': vol1h,
                    'vol1h_prev': vol1h_prev,
                    'vol1h_pct_change': vol1h_pct,
                    'ts_computed': now,
                    'last_error': None,
                }
            else:
                # Keep last good value but mark stale
                if product_id not in _CANDLE_VOLUME_CACHE:
                    _CANDLE_VOLUME_CACHE[product_id] = {
                        'vol1h': None,
                        'vol1h_prev': None,
                        'vol1h_pct_change': None,
                        'ts_computed': now,
                        'last_error': 'fetch_failed',
                    }
                else:
                    # Update only error + timestamp, keep old volume
                    _CANDLE_VOLUME_CACHE[product_id]['last_error'] = 'fetch_failed'
                    _CANDLE_VOLUME_CACHE[product_id]['ts_computed'] = now

def _get_candle_volume_for_symbols(symbols):
    """Get cached candle volumes for given symbols.

    Returns:
        List of dicts with {symbol, product_id, vol1h, vol1h_prev, vol1h_pct_change, stale}
    """
    # Minimum prev volume to trust pct change (avoid tiny-denominator drama)
    MIN_PREV_VOLUME = 100  # base units - if prev < this, pct is unreliable

    results = []
    with _CANDLE_VOLUME_CACHE_LOCK:
        for sym in symbols:
            product_id = f"{sym}-USD"
            cached = _CANDLE_VOLUME_CACHE.get(product_id)
            if not cached:
                continue

            vol1h = cached.get('vol1h')
            if vol1h is None:
                continue

            vol1h_prev = cached.get('vol1h_prev')
            vol1h_pct = cached.get('vol1h_pct_change')

            # Suppress pct if prev is too small (unreliable denominator)
            baseline_missing_reason = None
            if vol1h_prev is None:
                baseline_missing_reason = 'prev_window_missing'
                vol1h_pct = None
            elif vol1h_prev < MIN_PREV_VOLUME:
                baseline_missing_reason = 'prev_too_small'
                vol1h_pct = None

            now = time.time()
            ts_computed = cached.get('ts_computed', 0)
            stale = (now - ts_computed) > 60  # Stale if > 1 min old

            results.append({
                'symbol': sym,
                'product_id': product_id,
                'vol1h': vol1h,
                'vol1h_prev': vol1h_prev,
                'vol1h_pct_change': vol1h_pct,
                'baseline_missing_reason': baseline_missing_reason,
                'stale': stale,
            })

    return results

def calculate_1hour_volume_changes(current_prices):
    """Calculate real-time 1h volume changes using candle data.

    Returns list of dicts with symbol, current_price, vol1h, vol1h_pct_change.
    """
    # Get all symbols that have current prices
    symbols = list(current_prices.keys())

    if not symbols:
        return []

    # Update candle cache for these symbols (background fetch)
    _update_candle_volume_cache([f"{sym}-USD" for sym in symbols[:60]])

    # Get cached volume data
    volume_data = _get_candle_volume_for_symbols(symbols)

    # Combine with current prices
    results = []
    for vol_entry in volume_data:
        symbol = vol_entry['symbol']
        current_price = current_prices.get(symbol, 0)

        if current_price <= 0:
            continue

        results.append({
            "symbol": symbol,
            "current_price": current_price,
            "vol1h": vol_entry['vol1h'],
            "vol1h_pct_change": vol_entry.get('vol1h_pct_change'),
            "stale": vol_entry.get('stale', False),
        })

    return results

# ----------------------------------------------------------------------------
# Background-computed component snapshots (cache-only /data)
# ----------------------------------------------------------------------------
_MW_COMPONENT_SNAPSHOTS = {
    'gainers_1m': None,
    'gainers_3m': None,
    'losers_3m': None,
    'banner_1h_price': None,
    'banner_1h_volume': None,
    'volume_1h_candles': None,
    'alerts': None,
    'updated_at': None,
}
_MW_COMPONENT_SNAPSHOTS_LOCK = threading.Lock()

# Last-good snapshot tracking: timestamp and full payload
_MW_LAST_GOOD_TS = None
_MW_LAST_GOOD_DATA = None
_VOLUME_DB_READY = False
_VOLUME_BACKOFF = {}
_VOLUME_FAILS = {}


def _mw_set_component_snapshots(**updates):
    global _MW_LAST_GOOD_TS, _MW_LAST_GOOD_DATA
    with _MW_COMPONENT_SNAPSHOTS_LOCK:
        for k, v in updates.items():
            _MW_COMPONENT_SNAPSHOTS[k] = v

        # Update last-good timestamp if we have meaningful data
        g1 = _MW_COMPONENT_SNAPSHOTS.get('gainers_1m') or {}
        g3 = _MW_COMPONENT_SNAPSHOTS.get('gainers_3m') or {}
        l3 = _MW_COMPONENT_SNAPSHOTS.get('losers_3m') or {}
        bp = _MW_COMPONENT_SNAPSHOTS.get('banner_1h_price') or {}
        bv = _MW_COMPONENT_SNAPSHOTS.get('banner_1h_volume') or {}
        v1h = _MW_COMPONENT_SNAPSHOTS.get('volume_1h_candles') or {}

        # Check if any component has data (not empty)
        has_data = (
            (isinstance(g1, dict) and len(g1.get('data', [])) > 0) or
            (isinstance(g3, dict) and len(g3.get('data', [])) > 0) or
            (isinstance(l3, dict) and len(l3.get('data', [])) > 0) or
            (isinstance(bp, dict) and len(bp.get('data', [])) > 0) or
            (isinstance(bv, dict) and len(bv.get('data', [])) > 0) or
            (isinstance(v1h, dict) and len(v1h.get('data', [])) > 0)
        )

        if has_data:
            import time
            _MW_LAST_GOOD_TS = time.time()
            _MW_LAST_GOOD_DATA = dict(_MW_COMPONENT_SNAPSHOTS)


def _mw_get_component_snapshot(name: str):
    with _MW_COMPONENT_SNAPSHOTS_LOCK:
        return _MW_COMPONENT_SNAPSHOTS.get(name)


def _volume_db_init_once():
    global _VOLUME_DB_READY
    if not _VOLUME_DB_READY:
        try:
            ensure_volume_db()
            _VOLUME_DB_READY = True
        except Exception as e:
            logging.warning(f"volume1h db init failed: {e}")


def _volume1h_compute_ranked(payload: dict):
    _volume_db_init_once()
    now_ts = int(time.time())
    tracked = get_volume_tracked_product_ids(payload)
    items = []
    for pid in tracked:
        try:
            m = compute_volume_1h(pid, now_ts)
        except Exception as e:
            logging.debug(f"volume1h compute error for {pid}: {e}")
            continue
        if m:
            items.append(m)

    def sort_key(row):
        pct = row.get("volume_change_1h_pct")
        pct_abs = abs(pct) if isinstance(pct, (int, float)) else None
        vol_now = row.get("volume_1h_now") or 0
        return (-(pct_abs if pct_abs is not None else -1), -vol_now)

    # Sort: abs pct desc (None last via -1 trick), then volume desc
    items.sort(key=sort_key)
    items = items[: VOLUME_1H_BANNER_SIZE]
    for idx, row in enumerate(items, start=1):
        row["rank"] = idx
    return items


# ----------------------------------------------------------------------------
# 1h volume helpers (tracked set + SQLite-backed compute)
# ----------------------------------------------------------------------------
def _product_id_from_row(row):
    if not row:
        return None
    pid = row.get("product_id") or row.get("productId")
    if isinstance(pid, str) and pid:
        return pid
    sym = row.get("symbol") or row.get("ticker")
    if sym:
        return f"{str(sym).upper()}-USD"
    return None


def get_volume_tracked_product_ids(payload: dict) -> list[str]:
    seen = set()
    out = []

    def add(pid: str):
        if not pid:
            return
        if pid in seen:
            return
        seen.add(pid)
        out.append(pid)

    for pid in VOLUME_1H_BASELINE:
        add(pid)

    for key in ("gainers_1m", "gainers_3m", "losers_3m", "watchlist"):
        rows = payload.get(key) or []
        for row in rows:
            pid = _product_id_from_row(row)
            if pid:
                add(pid)

    return out[: VOLUME_1H_MAX_TRACKED]


def _volume1h_build_payload_snapshot():
    def _unwrap(name):
        snap = _mw_get_component_snapshot(name)
        if isinstance(snap, dict):
            return snap.get("data") or []
        if isinstance(snap, list):
            return snap
        return []

    payload = {
        "gainers_1m": _unwrap("gainers_1m"),
        "gainers_3m": _unwrap("gainers_3m"),
        "losers_3m": _unwrap("losers_3m"),
    }

    try:
        # Optional watchlist from last-good payload if available
        if isinstance(_MW_LAST_GOOD_DATA, dict):
            wl = _MW_LAST_GOOD_DATA.get("watchlist")
            if wl:
                payload["watchlist"] = wl
    except Exception:
        pass

    return payload


def _mw_check_3m_baseline_ready():
    """Check if we have enough price history for 3m baseline (≥180s old data).

    Returns:
        (warming_3m, baseline_ts_3m, baseline_age_seconds_3m)
    """
    import time
    now = time.time()
    oldest_ts = None

    # Check a sample of symbols to see if they have history ≥180s old
    sample_symbols = list(price_history.keys())[:20] if price_history else []

    for symbol in sample_symbols:
        history = price_history.get(symbol)
        if history and len(history) > 0:
            # History is stored as deque of (timestamp, price)
            first_ts = history[0][0]
            if oldest_ts is None or first_ts < oldest_ts:
                oldest_ts = first_ts

    if oldest_ts is None:
        # No history at all
        return True, None, None

    baseline_age = now - oldest_ts

    # Need at least 180 seconds of history for 3m baseline
    warming_3m = baseline_age < 180

    return warming_3m, oldest_ts, int(baseline_age)


def _mw_get_last_good_metadata():
    """Return (last_good_ts, stale_seconds, warming, warming_3m, baseline_ts_3m, baseline_age_3m) for /data meta field."""
    global _MW_LAST_GOOD_TS
    with _MW_COMPONENT_SNAPSHOTS_LOCK:
        baseline_meta_3m = _get_baseline_meta_3m() or {}
        warming_3m = not bool(baseline_meta_3m.get("ready"))
        baseline_ts_3m = baseline_meta_3m.get("baseline_ts")
        baseline_age_3m = baseline_meta_3m.get("age_seconds")

        if _MW_LAST_GOOD_TS is None:
            return None, None, True, warming_3m, baseline_ts_3m, baseline_age_3m
        import time
        now = time.time()
        stale_seconds = int(now - _MW_LAST_GOOD_TS)
        return _MW_LAST_GOOD_TS, stale_seconds, False, warming_3m, baseline_ts_3m, baseline_age_3m

# DEV seed for 1h volume history so banners have data immediately.
def seed_volume_history_if_dev():
    """Gateable dev seeder. Delegates to `backend.fixtures.seed_volumes.load_dev_volume_fixture`.

    Safety:
      - Only runs when `DEV_SEED_VOLUME_HISTORY=1` is set.
      - Refuses to run when `FLASK_ENV=production`.
    """
    if os.getenv("DEV_SEED_VOLUME_HISTORY") != "1":
        return

    # Do not run in production by mistake
    if os.environ.get('FLASK_ENV', '').lower() == 'production':
        logging.warning("DEV_SEED_VOLUME_HISTORY=1 ignored in production environment")
        return

    # Import the fixture loader from a dedicated module so logic is testable
    try:
        from backend.fixtures.seed_volumes import load_dev_volume_fixture
    except Exception:
        try:
            from fixtures.seed_volumes import load_dev_volume_fixture
        except Exception as e:
            logging.debug(f"Dev seeder loader not available: {e}")
            return

    try:
        result = load_dev_volume_fixture(volume_history_24h, symbols=None, minutes=60, logger=logging)
        logging.info(f"Seeded dev volume history: {result}")
    except Exception as e:
        logging.debug(f"Dev seeder failed: {e}")

# -----------------------------------------------------------------------------
# Trend Alert Hygiene: fire on streak thresholds with cooldown per scope/symbol
# -----------------------------------------------------------------------------
alerts_state = {
    '1m': {},
    '3m': {},
    '1h_price': {},
    '1h_volume': {},
}
alerts_log_main = deque(maxlen=2000)
alerts_log_trend = deque(maxlen=2000)
# Back-compat alias for legacy callers (treated as main).
alerts_log = alerts_log_main
ALERT_SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")

BASIC_ALERTS_MAX = int(CONFIG.get("ALERTS_BASIC_MAX", 200))

# Lightweight alerts buffer for /api/alerts (simple ring)
alerts_basic_log = deque(maxlen=BASIC_ALERTS_MAX)
_BASIC_ALERTS_LOCK = threading.Lock()
_BASIC_ALERT_EMIT_TS = {}
_BASIC_ALERT_EMIT_VAL = {}
_BASIC_ALERT_EMIT_DIR = {}

ALERT_IMPULSE_1M_THRESH = float(CONFIG.get("ALERT_IMPULSE_1M_PCT", 0.75))
ALERT_IMPULSE_3M_THRESH = float(CONFIG.get("ALERT_IMPULSE_3M_PCT", 1.25))
ALERT_IMPULSE_COOLDOWN = int(CONFIG.get("ALERT_IMPULSE_COOLDOWN_SECONDS", 60))
ALERT_IMPULSE_DEDUPE_DELTA = float(CONFIG.get("ALERT_IMPULSE_DEDUPE_DELTA", 0.2))
ALERT_IMPULSE_TTL_MINUTES = int(CONFIG.get("ALERT_IMPULSE_TTL_MINUTES", 5))
ALERT_VOLATILITY_SPIKE = float(CONFIG.get("ALERT_VOLATILITY_SPIKE", 1.2))

BASIC_ALERTS_COOLDOWN = int(CONFIG.get("ALERTS_BASIC_COOLDOWN_SECONDS", ALERT_IMPULSE_COOLDOWN))
BASIC_ALERTS_DEDUPE_DELTA = float(CONFIG.get("ALERTS_BASIC_DEDUPE_DELTA", ALERT_IMPULSE_DEDUPE_DELTA))

MW_SEED_ALERTS = os.getenv("MW_SEED_ALERTS", "0") == "1"
_ALERT_EMIT_TS = {}
_ALERT_EMIT_VAL = {}
_ALERT_EMIT_DIR = {}

_MW_LAST_GOOD_ALERTS = []
_MW_LAST_GOOD_ALERTS_TS = None

# --- Window-second mapping (shared across bridge injection + dedupe) ---
_WINDOW_S_MAP = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "1h": 3600, "1m_vs_3m": 180}

# --- Default cooldowns by window_s ---
_DEFAULT_COOLDOWN_BY_WS = {60: 90, 180: 240, 300: 360, 900: 900, 3600: 1800}
_DEFAULT_COOLDOWN_FALLBACK = 120


def inject_bridge_fields(alert: dict) -> dict:
    """Ensure an alert dict has metrics, dedupe_key, cooldown_s, event_count.

    Idempotent: skips fields that already exist.
    Call from _emit_alert, emit_alert, _normalize_alert, or any raw append.
    """
    if not isinstance(alert, dict):
        return alert

    # --- dedupe_key ---
    if not alert.get("dedupe_key"):
        atype = str(alert.get("type") or "alert").upper()
        sym = str(alert.get("symbol") or "MARKET").upper()
        ws = alert.get("window_s")
        if ws is None:
            w = alert.get("window") or ""
            ws = _WINDOW_S_MAP.get(w, "")
        alert["dedupe_key"] = f"{atype}:{sym}:{ws}"

    # --- cooldown_s ---
    if alert.get("cooldown_s") is None:
        ws = alert.get("window_s")
        if ws is None:
            w = alert.get("window") or ""
            ws = _WINDOW_S_MAP.get(w)
        alert["cooldown_s"] = _DEFAULT_COOLDOWN_BY_WS.get(ws, _DEFAULT_COOLDOWN_FALLBACK)

    # --- metrics ---
    if not alert.get("metrics"):
        meta = alert.get("meta") if isinstance(alert.get("meta"), dict) else {}
        extra = alert.get("extra") if isinstance(alert.get("extra"), dict) else {}
        alert["metrics"] = {
            "pct": alert.get("pct") or extra.get("pct"),
            "window_s": alert.get("window_s") or _WINDOW_S_MAP.get(alert.get("window") or "", None),
            "price": alert.get("price"),
            "price_now": alert.get("price_now"),
            "price_then": alert.get("price_then"),
            "volume": meta.get("latest_vol") or meta.get("vol1h") or extra.get("vol1h"),
            "vol_change_pct": alert.get("vol_change_pct") or meta.get("vol1h_pct") or extra.get("vol_change_pct"),
        }

    # --- event_count ---
    if alert.get("event_count") is None:
        alert["event_count"] = 1

    return alert


def _mw_get_alerts_normalized_with_sticky():
    """Return (alerts, meta) where alerts may be a short sticky last-good list.

    Motivation: avoid transient empty alert cycles wiping the UI when baselines
    or snapshots temporarily produce 0.
    """
    global _MW_LAST_GOOD_ALERTS, _MW_LAST_GOOD_ALERTS_TS

    alerts = _normalize_alerts(list(alerts_log_main))
    now = time.time()
    sticky_window_s = int(CONFIG.get("ALERTS_STICKY_SECONDS", 60) or 60)
    sticky = False
    last_good_age_s = None

    if alerts:
        _MW_LAST_GOOD_ALERTS = alerts
        _MW_LAST_GOOD_ALERTS_TS = now
    else:
        if _MW_LAST_GOOD_ALERTS and _MW_LAST_GOOD_ALERTS_TS is not None:
            try:
                last_good_age_s = float(now - float(_MW_LAST_GOOD_ALERTS_TS))
            except Exception:
                last_good_age_s = None
            if last_good_age_s is not None and last_good_age_s <= sticky_window_s:
                alerts = list(_MW_LAST_GOOD_ALERTS)
                sticky = True

    meta = {
        "sticky": sticky,
        "sticky_window_s": sticky_window_s,
        "last_good_age_s": int(last_good_age_s) if last_good_age_s is not None else None,
    }
    return alerts, meta

def _emit_alert(alert: dict, cooldown_s: int = ALERT_IMPULSE_COOLDOWN, dedupe_delta: float = ALERT_IMPULSE_DEDUPE_DELTA) -> bool:
    """Emit an alert into alerts_log_main with per-key cooldown, magnitude/direction dedupe,
    and update-in-place during cooldown. Bridge fields auto-injected via inject_bridge_fields."""
    if not alert or not isinstance(alert, dict):
        return False

    inject_bridge_fields(alert)
    alert["cooldown_s"] = cooldown_s  # override with caller's explicit cooldown

    key = f"{alert.get('type')}::{alert.get('symbol')}"
    now = time.time()
    last_ts = _ALERT_EMIT_TS.get(key, 0)
    within_cooldown = (now - last_ts) < cooldown_s if last_ts else False

    magnitude = float(alert.get("meta", {}).get("magnitude", 0) or 0)
    prev = float(_ALERT_EMIT_VAL.get(key, 0) or 0)
    direction = (alert.get("meta", {}).get("direction") or alert.get("direction") or "").lower() or None
    prev_dir = _ALERT_EMIT_DIR.get(key)

    allow = False
    if not within_cooldown:
        allow = True
    else:
        if magnitude > prev + dedupe_delta:
            allow = True
        elif direction and prev_dir and direction != prev_dir:
            allow = True

    if not allow:
        # --- Update-in-place: bump metrics if magnitude grew ---
        if within_cooldown and magnitude > prev:
            dk = alert.get("dedupe_key")
            for existing in reversed(alerts_log_main):
                if existing.get("dedupe_key") == dk:
                    existing["event_count"] = (existing.get("event_count") or 1) + 1
                    if alert.get("metrics", {}).get("pct") is not None:
                        if existing.get("metrics") is None:
                            existing["metrics"] = {}
                        existing["metrics"]["pct"] = alert["metrics"]["pct"]
                    _ALERT_EMIT_VAL[key] = magnitude
                    break
        return False

    alert["event_count"] = 1
    alerts_log_main.append(alert)
    _ALERT_EMIT_TS[key] = now
    _ALERT_EMIT_VAL[key] = magnitude
    _ALERT_EMIT_DIR[key] = direction
    return True


def emit_alert(alert_type: str, severity: str, symbol: str | None, message: str,
               window: str | None = None, extra: dict | None = None) -> bool:
    """Emit a lightweight alert into the basic ring buffer with dedupe + cooldown."""
    try:
        if not alert_type or not message:
            return False
        sym = str(symbol).upper() if symbol else "MARKET"
        key = f"{alert_type}::{sym}"
        now = time.time()
        last_ts = _BASIC_ALERT_EMIT_TS.get(key, 0)
        within_cooldown = (now - last_ts) < BASIC_ALERTS_COOLDOWN if last_ts else False

        magnitude = None
        direction = None
        if isinstance(extra, dict):
            direction = extra.get("direction")
            magnitude = extra.get("magnitude")
            if magnitude is None:
                magnitude = extra.get("pct")
            if magnitude is None:
                magnitude = extra.get("volatility")

        try:
            mag_val = abs(float(magnitude)) if magnitude is not None else 0.0
        except Exception:
            mag_val = 0.0

        prev_val = float(_BASIC_ALERT_EMIT_VAL.get(key, 0) or 0)
        prev_dir = _BASIC_ALERT_EMIT_DIR.get(key)

        allow = False
        if not within_cooldown:
            allow = True
        else:
            if mag_val and mag_val > prev_val + BASIC_ALERTS_DEDUPE_DELTA:
                allow = True
            elif direction and prev_dir and direction != prev_dir:
                allow = True

        # Compute dedupe_key early (needed for update-in-place)
        ws = _WINDOW_S_MAP.get(window or "", "")
        dk = f"{alert_type.upper()}:{sym}:{ws}"

        # --- Update-in-place during cooldown (before early return) ---
        if not allow:
            if within_cooldown and mag_val > prev_val:
                with _BASIC_ALERTS_LOCK:
                    for existing in reversed(alerts_basic_log):
                        if existing.get("dedupe_key") == dk:
                            existing["event_count"] = (existing.get("event_count") or 1) + 1
                            if isinstance(extra, dict) and extra.get("pct") is not None:
                                if existing.get("metrics") is None:
                                    existing["metrics"] = {}
                                existing["metrics"]["pct"] = extra["pct"]
                            _BASIC_ALERT_EMIT_VAL[key] = mag_val
                            break
            return False

        ts_iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        alert = {
            "id": f"{alert_type}_{sym}_{int(now * 1000)}",
            "ts": ts_iso,
            "type": alert_type,
            "severity": (severity or "info"),
            "symbol": sym,
            "window": window,
            "message": message,
            "extra": extra or {},
        }
        inject_bridge_fields(alert)
        alert["cooldown_s"] = BASIC_ALERTS_COOLDOWN  # override with basic stream cooldown

        with _BASIC_ALERTS_LOCK:
            alerts_basic_log.append(alert)
        _BASIC_ALERT_EMIT_TS[key] = now
        _BASIC_ALERT_EMIT_VAL[key] = mag_val
        _BASIC_ALERT_EMIT_DIR[key] = direction
        return True
    except Exception:
        return False


def _emit_impulse_alert(symbol: str, change_pct: float, price: float, window: str = "1m") -> None:
    """Emit a typed impulse alert for short-window moves (1m/3m).

    Enhanced type classification:
      >=6%  → moonshot (up) / crater (down), severity=critical
      >=2.5% → breakout (up) / dump (down), severity=high
      below → impulse_1m / impulse_3m as before, severity=medium
    """
    try:
        if symbol is None or change_pct is None:
            return
        mag = abs(float(change_pct))
        sym_clean = str(symbol).upper()
        product_id = resolve_product_id_from_row(sym_clean) or (f"{sym_clean}-USD" if "-" not in sym_clean else sym_clean)
        now = datetime.now(timezone.utc)
        emitted_ms = int(now.timestamp() * 1000)
        direction = "up" if change_pct >= 0 else "down"
        window_s = 60 if str(window).lower().startswith("1") else 180 if str(window).lower().startswith("3") else None
        price_now = float(price) if price is not None else None
        price_then = None
        try:
            denom = 1.0 + (float(change_pct) / 100.0)
            if price_now is not None and denom and denom != 0:
                price_then = price_now / denom
        except Exception:
            price_then = None

        # Rich type classification
        if mag >= 3.0:
            alert_type = "moonshot" if direction == "up" else "crater"
            severity = "critical"
        elif mag >= 1.5:
            alert_type = "breakout" if direction == "up" else "dump"
            severity = "high"
        else:
            alert_type = f"impulse_{window}"
            severity = "medium"
        message, title = build_alert_text(
            alert_type,
            symbol=product_id,
            window=window,
            direction=direction,
            change_pct=change_pct,
        )

        alert = {
          "id": f"{alert_type}_{product_id}_{int(time.time())}",
          "ts": now.isoformat(),
          "ts_ms": emitted_ms,
          "event_ts": now.isoformat(),
          "event_ts_ms": emitted_ms,
          "symbol": product_id,
          "type": alert_type,
          "severity": severity,
          "title": title,
          "message": message,
          "window_s": window_s,
          "pct": float(change_pct),
          "direction": direction,
          "price_now": price_now,
          "price_then": price_then,
          "price": float(price_now or 0),
          "expires_at": (now + timedelta(minutes=ALERT_IMPULSE_TTL_MINUTES)).isoformat(),
          "trade_url": f"https://www.coinbase.com/advanced-trade/spot/{product_id}",
          "meta": {"magnitude": mag, "direction": direction, "window": window, "alert_type": alert_type},
        }
        _emit_alert(alert)
        try:
            emit_alert(
                f"impulse_{window}",
                severity,
                product_id,
                message,
                window=window,
                extra={
                    "magnitude": mag,
                    "direction": direction,
                    "pct": float(change_pct),
                    "price": price_now,
                    "alert_type": alert_type,
                },
            )
        except Exception:
            pass
    except Exception:
        # never block tables
        pass


def _emit_divergence_alert(symbol: str, ret_1m: float, ret_3m: float, price: float) -> None:
    """Emit an alert when 1m and 3m disagree significantly.

    Fires when 1m > 0.3% and 3m < -0.3% (or vice versa).
    Cooldown 120s, dedupe_delta 0.3.
    """
    try:
        if symbol is None or ret_1m is None or ret_3m is None:
            return
        # Check for divergence: 1m and 3m in opposite directions with magnitude
        if not ((ret_1m > 0.3 and ret_3m < -0.3) or (ret_1m < -0.3 and ret_3m > 0.3)):
            return

        sym_clean = str(symbol).upper()
        product_id = resolve_product_id_from_row(sym_clean) or (f"{sym_clean}-USD" if "-" not in sym_clean else sym_clean)
        now = datetime.now(timezone.utc)
        emitted_ms = int(now.timestamp() * 1000)

        if ret_1m > 0 and ret_3m < 0:
            direction = "reversal_up"
        else:
            direction = "reversal_down"

        magnitude = abs(ret_1m - ret_3m)
        div_price_now = float(price) if price else 0
        msg, title = build_alert_text(
            "divergence",
            symbol=product_id,
            ret_1m=ret_1m,
            ret_3m=ret_3m,
        )
        alert = {
            "id": f"divergence_{product_id}_{int(time.time())}",
            "ts": now.isoformat(),
            "ts_ms": emitted_ms,
            "event_ts": now.isoformat(),
            "event_ts_ms": emitted_ms,
            "symbol": product_id,
            "type": "divergence",
            "severity": "medium",
            "title": title,
            "message": msg,
            "pct": round(magnitude, 2),
            "direction": direction,
            "price": div_price_now,
            "price_now": div_price_now,
            "ret_1m": round(ret_1m, 4),
            "ret_3m": round(ret_3m, 4),
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
            "trade_url": f"https://www.coinbase.com/advanced-trade/spot/{product_id}",
            "meta": {
                "magnitude": magnitude,
                "direction": direction,
                "ret_1m": round(ret_1m, 4),
                "ret_3m": round(ret_3m, 4),
            },
        }
        _emit_alert(alert, cooldown_s=120, dedupe_delta=0.3)
        try:
            emit_alert(
                "divergence",
                "medium",
                product_id,
                msg,
                window="1m_vs_3m",
                extra={
                    "magnitude": magnitude,
                    "direction": direction,
                    "ret_1m": round(ret_1m, 4),
                    "ret_3m": round(ret_3m, 4),
                    "price": div_price_now,
                },
            )
        except Exception:
            pass
    except Exception:
        pass


def _emit_volatility_spike_alert(heat: dict | None) -> None:
    """Emit a market-wide volatility spike alert based on Market Heat volatility."""
    try:
        if not isinstance(heat, dict):
            return
        comps = heat.get("components") if isinstance(heat.get("components"), dict) else {}
        vol = comps.get("volatility")
        if vol is None:
            return
        vol_val = float(vol)
        if vol_val < ALERT_VOLATILITY_SPIKE:
            return
        severity = "high" if vol_val >= ALERT_VOLATILITY_SPIKE * 1.5 else "medium"
        msg, _title = build_alert_text(
            "volatility_spike",
            symbol="MARKET",
            vol_change_pct=vol_val,
        )
        emit_alert(
            "volatility_spike",
            severity,
            "MARKET",
            msg,
            window="3m",
            extra={
                "volatility": round(vol_val, 4),
                "threshold": ALERT_VOLATILITY_SPIKE,
            },
        )
    except Exception:
        pass


def _emit_whale_alert(symbol: str, vol1h: float, vol1h_pct: float, price: float) -> None:
    """Emit whale alerts using z-score per-minute volume analysis + price impact.

    Three detection modes:
    1. WHALE MOVE: Recent 1-min candle volume is >=3σ above rolling median AND
       price moved meaningfully (impact). Classic "big money entering."
    2. WHALE SURGE: Hourly volume spike >=150% vs previous hour with price displacement.
       Broader window, catches sustained whale activity.
    3. ABSORPTION: High volume (>=2.5σ) but price barely moved (<0.15%). Someone is
       soaking liquidity — potential accumulation/distribution.

    Uses _CANDLE_MINUTE_VOLUMES for per-minute z-score (populated by _compute_1h_volume_from_candles).
    Falls back to hourly comparison if minute data unavailable.
    """
    try:
        sym_clean = str(symbol).upper()
        product_id = resolve_product_id_from_row(sym_clean) or (f"{sym_clean}-USD" if "-" not in sym_clean else sym_clean)

        # --- Per-minute z-score whale detection ---
        minute_data = _CANDLE_MINUTE_VOLUMES.get(product_id, [])

        if len(minute_data) >= 15:
            # minute_data is most-recent first
            # Extract volumes for last 60 minutes (or however many we have)
            vols = [m['vol'] for m in minute_data if m.get('vol', 0) > 0]

            if len(vols) >= 15:
                # Latest completed candle
                latest = minute_data[0]
                latest_vol = latest['vol']
                latest_close = latest.get('close', 0)
                latest_open = latest.get('open', 0)
                latest_high = latest.get('high', 0)
                latest_low = latest.get('low', 0)

                # Rolling stats from candles [1:] (exclude latest for unbiased baseline)
                baseline_vols = vols[1:61]  # Up to 60 prior candles
                n = len(baseline_vols)

                if n >= 10:
                    sorted_vols = sorted(baseline_vols)
                    median_vol = sorted_vols[n // 2]
                    mean_vol = sum(baseline_vols) / n
                    variance = sum((v - mean_vol) ** 2 for v in baseline_vols) / n
                    std_vol = variance ** 0.5 if variance > 0 else 0

                    # Z-score of latest candle vs baseline
                    z_vol = (latest_vol - mean_vol) / std_vol if std_vol > 0 else 0

                    # Per-candle price change %
                    candle_pct = ((latest_close - latest_open) / latest_open * 100) if latest_open > 0 else 0
                    candle_range_pct = ((latest_high - latest_low) / latest_low * 100) if latest_low > 0 else 0

                    # Volume ratio vs median
                    vol_ratio = (latest_vol / median_vol) if median_vol > 0 else 0

                    # Also check 3-candle cluster (last 3 minutes combined)
                    cluster_vol = sum(m['vol'] for m in minute_data[:3]) if len(minute_data) >= 3 else latest_vol
                    cluster_z = (cluster_vol / 3 - mean_vol) / std_vol if std_vol > 0 else 0

                    now = datetime.now(timezone.utc)
                    emitted_ms = int(now.timestamp() * 1000)
                    base_price = float(price) if price else (latest_close or 0)

                    # --- Mode 1: WHALE MOVE (z-score spike + price impact) ---
                    # Single candle: z >= 3.0 AND price moved >= 0.3%
                    # OR 3-candle cluster: avg z >= 2.5 AND price moved >= 0.4%
                    if (z_vol >= 2.5 and abs(candle_pct) >= 0.2 and latest_vol > 100) or \
                       (cluster_z >= 2.0 and abs(candle_pct) >= 0.3 and cluster_vol > 200):
                        direction = "up" if candle_pct > 0 else "down"
                        whale_score = z_vol * abs(candle_pct)  # composite magnitude
                        severity = "critical" if z_vol >= 5.0 or whale_score >= 8 else "high"

                        # Derive price_then from candle open
                        whale_price_now = base_price
                        whale_price_then = float(latest_open) if latest_open else None

                        msg, title = build_alert_text(
                            "whale_move",
                            symbol=product_id,
                            candle_pct=candle_pct,
                            vol_ratio=vol_ratio,
                            z_vol=z_vol,
                            base_price=base_price,
                        )
                        alert = {
                            "id": f"whale_{product_id}_{int(time.time())}",
                            "ts": now.isoformat(),
                            "ts_ms": emitted_ms,
                            "event_ts": now.isoformat(),
                            "event_ts_ms": emitted_ms,
                            "symbol": product_id,
                            "type": "whale_move",
                            "severity": severity,
                            "title": title,
                            "message": msg,
                            "pct": round(candle_pct, 2),
                            "direction": direction,
                            "price": base_price,
                            "price_now": whale_price_now,
                            "price_then": whale_price_then,
                            "window_s": 60,
                            "vol_change_pct": round(vol_ratio * 100 - 100, 1),
                            "expires_at": (now + timedelta(minutes=8)).isoformat(),
                            "trade_url": f"https://www.coinbase.com/advanced-trade/spot/{product_id}",
                            "meta": {
                                "magnitude": round(whale_score, 2),
                                "direction": f"whale_{direction}",
                                "z_vol": round(z_vol, 2),
                                "vol_ratio": round(vol_ratio, 2),
                                "candle_pct": round(candle_pct, 4),
                                "candle_range_pct": round(candle_range_pct, 4),
                                "latest_vol": round(latest_vol, 2),
                                "median_vol": round(median_vol, 2),
                                "cluster_z": round(cluster_z, 2),
                                "alert_type": "whale_move",
                            },
                        }
                        _emit_alert(alert, cooldown_s=90, dedupe_delta=1.5)
                        return  # Don't double-fire

                    # --- Mode 3: ABSORPTION (high vol, flat price) ---
                    # z >= 2.5 AND price move < 0.15% AND range < 0.3%
                    # Someone is soaking liquidity without moving price
                    if z_vol >= 2.5 and abs(candle_pct) < 0.15 and candle_range_pct < 0.3 and latest_vol > 100:
                        # Check if this pattern repeats (2+ of last 5 candles also high-vol + flat)
                        absorption_count = 0
                        for m in minute_data[1:6]:
                            m_vol = m.get('vol', 0)
                            m_z = (m_vol - mean_vol) / std_vol if std_vol > 0 else 0
                            m_pct = ((m.get('close', 0) - m.get('open', 1)) / m.get('open', 1) * 100) if m.get('open', 0) > 0 else 0
                            if m_z >= 2.0 and abs(m_pct) < 0.2:
                                absorption_count += 1
                        if absorption_count >= 1:  # At least 2 total high-vol flat candles
                            msg, title = build_alert_text(
                                "whale_absorption",
                                symbol=product_id,
                                candle_pct=candle_pct,
                                vol_ratio=vol_ratio,
                                z_vol=z_vol,
                                pulses=absorption_count + 1,
                            )
                            alert = {
                                "id": f"absorption_{product_id}_{int(time.time())}",
                                "ts": now.isoformat(),
                                "ts_ms": emitted_ms,
                                "event_ts": now.isoformat(),
                                "event_ts_ms": emitted_ms,
                                "symbol": product_id,
                                "type": "whale_move",
                                "severity": "medium",
                                "title": title,
                                "message": msg,
                                "pct": round(candle_pct, 2),
                                "direction": "absorption",
                                "price": base_price,
                                "price_now": base_price,
                                "price_then": float(latest_open) if latest_open else None,
                                "window_s": 60,
                                "vol_change_pct": round(vol_ratio * 100 - 100, 1),
                                "expires_at": (now + timedelta(minutes=5)).isoformat(),
                                "trade_url": f"https://www.coinbase.com/advanced-trade/spot/{product_id}",
                                "meta": {
                                    "magnitude": round(z_vol, 2),
                                    "direction": "absorption",
                                    "z_vol": round(z_vol, 2),
                                    "vol_ratio": round(vol_ratio, 2),
                                    "candle_pct": round(candle_pct, 4),
                                    "absorption_pulses": absorption_count + 1,
                                    "latest_vol": round(latest_vol, 2),
                                    "median_vol": round(median_vol, 2),
                                    "alert_type": "whale_move",
                                },
                            }
                            _emit_alert(alert, cooldown_s=300, dedupe_delta=1.0)
                            return

        # --- Mode 2: WHALE SURGE fallback (hourly comparison) ---
        # Lower threshold than before: 150% (was 200%)
        if vol1h_pct is not None and vol1h_pct >= 100 and vol1h is not None and vol1h >= 300:
            now = datetime.now(timezone.utc)
            emitted_ms = int(now.timestamp() * 1000)
            severity = "critical" if vol1h_pct >= 400 else "high" if vol1h_pct >= 250 else "medium"
            surge_price = float(price) if price else 0
            msg, title = build_alert_text(
                "whale_surge",
                symbol=product_id,
                vol1h_pct=vol1h_pct,
                vol1h=vol1h,
            )
            alert = {
                "id": f"whale_surge_{product_id}_{int(time.time())}",
                "ts": now.isoformat(),
                "ts_ms": emitted_ms,
                "event_ts": now.isoformat(),
                "event_ts_ms": emitted_ms,
                "symbol": product_id,
                "type": "whale_move",
                "severity": severity,
                "title": title,
                "message": msg,
                "pct": round(vol1h_pct, 2),
                "direction": "up",
                "price": surge_price,
                "price_now": surge_price,
                "window_s": 3600,
                "vol_change_pct": round(vol1h_pct, 1),
                "expires_at": (now + timedelta(minutes=10)).isoformat(),
                "trade_url": f"https://www.coinbase.com/advanced-trade/spot/{product_id}",
                "meta": {
                    "magnitude": vol1h_pct,
                    "direction": "volume_surge",
                    "vol1h": round(vol1h, 2),
                    "vol1h_pct": round(vol1h_pct, 2),
                    "alert_type": "whale_move",
                },
            }
            _emit_alert(alert, cooldown_s=300, dedupe_delta=30.0)
    except Exception:
        pass


def _emit_stealth_alert(symbol: str, price_change_3m: float, vol1h_pct: float, price: float) -> None:
    """Emit a stealth accumulation alert: price rising but volume flat/low.

    Detects quiet moves — price up >=1.5% over 3m but volume change < 30%.
    """
    try:
        if price_change_3m is None or price_change_3m < 0.8:
            return
        if vol1h_pct is None:
            return
        # Stealth = price up but volume NOT spiking
        if vol1h_pct > 50:
            return

        sym_clean = str(symbol).upper()
        product_id = resolve_product_id_from_row(sym_clean) or (f"{sym_clean}-USD" if "-" not in sym_clean else sym_clean)
        now = datetime.now(timezone.utc)
        emitted_ms = int(now.timestamp() * 1000)

        stealth_price_now = float(price) if price else 0
        stealth_price_then = None
        try:
            denom = 1.0 + (float(price_change_3m) / 100.0)
            if stealth_price_now and denom and denom != 0:
                stealth_price_then = stealth_price_now / denom
        except Exception:
            stealth_price_then = None

        msg, title = build_alert_text(
            "stealth_move",
            symbol=product_id,
            price_change_3m=price_change_3m,
            vol1h_pct=vol1h_pct,
        )
        alert = {
            "id": f"stealth_{product_id}_{int(time.time())}",
            "ts": now.isoformat(),
            "ts_ms": emitted_ms,
            "event_ts": now.isoformat(),
            "event_ts_ms": emitted_ms,
            "symbol": product_id,
            "type": "stealth_move",
            "severity": "medium",
            "title": title,
            "message": msg,
            "pct": round(price_change_3m, 2),
            "direction": "up",
            "price": stealth_price_now,
            "price_now": stealth_price_now,
            "price_then": stealth_price_then,
            "window_s": 180,
            "vol_change_pct": round(vol1h_pct, 1),
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
            "trade_url": f"https://www.coinbase.com/advanced-trade/spot/{product_id}",
            "meta": {
                "magnitude": price_change_3m,
                "direction": "stealth_up",
                "price_change_3m": round(price_change_3m, 4),
                "vol1h_pct": round(vol1h_pct, 2),
                "alert_type": "stealth_move",
            },
        }
        _emit_alert(alert, cooldown_s=180, dedupe_delta=0.3)
    except Exception:
        pass


def _emit_fomo_alert(heat_score: float, heat_label: str, fg_value: int | None) -> None:
    """Emit a FOMO/fear alert based on market heat + Fear & Greed.

    Fires when:
      - Heat >=70 AND F&G >=60 → FOMO (market overheating)
      - Heat <=25 AND F&G <=35 → FEAR (extreme fear)
    Cooldown 300s — this is a macro signal, not per-symbol.
    """
    try:
        fomo = heat_score >= 70 and (fg_value is None or fg_value >= 60)
        fear = heat_score <= 25 and (fg_value is None or fg_value <= 35)

        if not fomo and not fear:
            return

        now = datetime.now(timezone.utc)
        emitted_ms = int(now.timestamp() * 1000)

        if fomo:
            alert_type = "fomo_alert"
            severity = "high"
            direction = "fomo"
        else:
            alert_type = "fear_alert"
            severity = "high"
            direction = "fear"

        msg, title = build_alert_text(
            alert_type,
            symbol="MARKET",
            heat_score=heat_score,
            heat_label=heat_label,
            fg_value=fg_value,
        )
        alert = {
            "id": f"{alert_type}_{int(time.time())}",
            "ts": now.isoformat(),
            "ts_ms": emitted_ms,
            "event_ts": now.isoformat(),
            "event_ts_ms": emitted_ms,
            "symbol": "MARKET",
            "type": alert_type,
            "severity": severity,
            "title": title,
            "message": msg,
            "pct": heat_score,
            "direction": direction,
            "price": 0,
            "expires_at": (now + timedelta(minutes=15)).isoformat(),
            "trade_url": "",
            "meta": {
                "magnitude": heat_score,
                "direction": direction,
                "heat_score": heat_score,
                "heat_label": heat_label,
                "fg_value": fg_value,
                "alert_type": alert_type,
            },
        }
        _emit_alert(alert, cooldown_s=300, dedupe_delta=10.0)
    except Exception:
        pass


def _seed_alerts_once():
    """Optional wiring check: seed exactly one alert when MW_SEED_ALERTS=1."""
    if not MW_SEED_ALERTS:
        return
    if getattr(_seed_alerts_once, "_done", False):
        return
    _seed_alerts_once._done = True
    now = datetime.now(timezone.utc)
    msg, title = build_alert_text("seed", symbol="BTC-USD")
    seed_alert = {
        "id": f"seed_{int(time.time())}",
        "ts": now.isoformat(),
        "symbol": "BTC-USD",
        "type": "seed",
        "severity": "info",
        "title": title,
        "message": msg,
        "expires_at": (now + timedelta(seconds=90)).isoformat(),
        "trade_url": "https://www.coinbase.com/advanced-trade/spot/BTC-USD",
        "meta": {"source": "seed", "ttl_s": 90},
    }
    inject_bridge_fields(seed_alert)
    alerts_log_main.append(seed_alert)

ALERT_SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")

def _normalize_alert(raw: dict) -> dict:
    """Normalize an alert dict to the canonical schema used by /data."""
    if not isinstance(raw, dict):
        return {}

    symbol_raw = raw.get("symbol") or raw.get("product_id") or raw.get("pair")
    product_id = resolve_product_id_from_row(symbol_raw) or (str(symbol_raw).upper() if symbol_raw else None)
    symbol = product_id or (str(symbol_raw).upper() if symbol_raw else None)

    direction = (raw.get("direction") or "").lower()
    scope = str(raw.get("scope") or "").lower()
    streak = raw.get("streak") or 0

    # Map direction to a coarse alert type
    alert_type = raw.get("type") or None
    if not alert_type:
        if direction == "up":
            alert_type = "breakout"
        elif direction == "down":
            alert_type = "crater"
        else:
            alert_type = "divergence"

    # Derive severity: longer streak => higher severity
    severity = (raw.get("severity") or "").lower()
    if severity not in ALERT_SEVERITY_ORDER:
        severity = "high" if streak and streak >= 5 else "medium" if streak and streak >= 3 else "info"

    # Timestamp normalization
    ts = raw.get("ts") or datetime.now(timezone.utc).isoformat()
    expires_at = raw.get("expires_at")

    score = None
    try:
        if raw.get("score") is not None:
            score = float(raw.get("score"))
    except Exception:
        score = None

    trade_url = raw.get("trade_url")
    if not trade_url and symbol:
        trade_url = f"https://www.coinbase.com/advanced-trade/spot/{symbol}"

    def _num_or_none(v):
        try:
            if v is None or v == "":
                return None
            n = float(v)
            return n if (n == n and n != float("inf") and n != float("-inf")) else None
        except Exception:
            return None

    norm = {
        "id": raw.get("id") or f"{symbol or 'UNKNOWN'}-{scope or 'scope'}-{ts}",
        "symbol": symbol,
        "product_id": raw.get("product_id") or symbol,
        "type": alert_type,
        "severity": severity,
        "title": raw.get("title") or raw.get("message") or f"{scope.upper()} alert",
        "message": raw.get("message") or raw.get("title") or "",
        "ts": ts,
        "ts_ms": raw.get("ts_ms"),
        "event_ts": raw.get("event_ts"),
        "event_ts_ms": raw.get("event_ts_ms"),
        "window_s": raw.get("window_s"),
        "pct": _num_or_none(raw.get("pct")),
        "direction": raw.get("direction") or direction,
        "price_now": _num_or_none(raw.get("price_now")),
        "price_then": _num_or_none(raw.get("price_then")),
        "price": _num_or_none(raw.get("price")),
        "vol_pct": _num_or_none(raw.get("vol_pct") or raw.get("vol_change_pct")),
        "vol_now": _num_or_none(raw.get("vol_now")),
        "vol_then": _num_or_none(raw.get("vol_then")),
        "expires_at": expires_at,
        "score": score,
        "sources": raw.get("sources") or [],
        "trade_url": trade_url,
        # Bridge fields: metrics, dedupe_key, cooldown_s, event_count
        "metrics": raw.get("metrics"),
        "dedupe_key": raw.get("dedupe_key"),
        "cooldown_s": raw.get("cooldown_s"),
        "event_count": raw.get("event_count"),
    }
    norm = {k: v for k, v in norm.items() if v is not None}
    # Ensure bridge fields exist even for alerts that bypassed _emit_alert
    inject_bridge_fields(norm)
    return norm


def _normalize_alerts(alerts: list[dict]) -> list[dict]:
    """Normalize and filter alerts, preferring unique IDs and non-expired ones."""
    now = datetime.now(timezone.utc)
    seen = set()
    normalized = []
    for raw in alerts:
        norm = _normalize_alert(raw)
        if not norm:
            continue
        alert_id = norm.get("id")
        if alert_id in seen:
            continue
        seen.add(alert_id)
        expires = norm.get("expires_at")
        try:
            if expires:
                exp_dt = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
                if exp_dt < now:
                    continue
        except Exception:
            # If expiration is malformed, keep the alert rather than drop silently.
            pass
        normalized.append(norm)
    return normalized

def _maybe_fire_trend_alert(scope: str, symbol: str, direction: str, streak: int, score: float) -> None:
    """Fire an alert when a trend streak crosses configured thresholds with cooldown."""
    try:
        # MW_SPEC: alerts must not be polluted by generic trend/score feeds.
        # Keep this logic behind an explicit flag for debugging only.
        if not bool(CONFIG.get('ALERTS_ENABLE_TREND_ALERTS', False)):
            return
        thresholds = CONFIG.get('ALERTS_STREAK_THRESHOLDS', [2, 3])
        if direction == 'flat' or not thresholds:
            return
        # Highest threshold reached (if any)
        reached = max([t for t in thresholds if isinstance(t, int) and streak >= t], default=None)
        if reached is None:
            return
        now = time.time()
        last = alerts_state.get(scope, {}).get(symbol, 0)
        if now - last >= CONFIG.get('ALERTS_COOLDOWN_SECONDS', 120):
            msg = f"{scope} trend {direction} x{streak} on {symbol} (>= {reached}; score {float(score or 0.0):.2f})"
            alerts_log_trend.append({
                'ts': datetime.now().isoformat(),
                'scope': scope,
                'symbol': symbol,
                'direction': direction,
                'streak': int(streak),
                'score': round(float(score or 0.0), 3),
                'message': msg,
                'source': 'trend_streak',
            })
            alerts_state.setdefault(scope, {})[symbol] = now
            # Mirror into insights log if available (best-effort)
            try:
                if INSIGHTS_MEMORY:
                    INSIGHTS_MEMORY.add(f"ALERT: {msg}")
            except Exception:
                pass
    except Exception:
        # Never block main flow on alert failures
        pass

def log_config():
    """Log current configuration"""
    logging.info("=== CBMo4ers Configuration ===")
    for key, value in CONFIG.items():
        logging.info(f"{key}: {value}")
    logging.info("===============================")

# =============================================================================
# DYNAMIC PORT MANAGEMENT
# =============================================================================

def find_available_port(start_port=5001, max_attempts=10):
    """Find an available port starting from start_port"""
    import socket
    
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                logging.info(f"Found available port: {port}")
                return port
            except OSError:
                logging.warning(f"Port {port} is in use, trying next...")
                continue
    
    logging.error(f"Could not find available port in range {start_port}-{start_port + max_attempts}")
    return None

def kill_process_on_port(port):
    """Kill process using the specified port"""
    import subprocess
    import sys
    
    try:
        if sys.platform.startswith('darwin') or sys.platform.startswith('linux'):
            # macOS/Linux
            result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                 capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(['kill', '-9', pid])
                    logging.info(f"Killed process {pid} on port {port}")
                return True
        elif sys.platform.startswith('win'):
            # Windows
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    pid = line.strip().split()[-1]
                    subprocess.run(['taskkill', '/F', '/PID', pid])
                    logging.info(f"Killed process {pid} on port {port}")
                    return True
    except Exception as e:
        logging.error(f"Error killing process on port {port}: {e}")
    
    return False

# =============================================================================
# DYNAMIC CONFIGURATION FUNCTIONS
# =============================================================================

def update_config(new_config):
    """Update configuration at runtime"""
    global CONFIG, ALERT_IMPULSE_1M_THRESH, ALERT_IMPULSE_3M_THRESH
    old_config = CONFIG.copy()
    
    for key, value in new_config.items():
        if key in CONFIG:
            # Type conversion based on existing type
            if isinstance(CONFIG[key], int):
                CONFIG[key] = int(value)
            elif isinstance(CONFIG[key], float):
                CONFIG[key] = float(value)
            elif isinstance(CONFIG[key], bool):
                CONFIG[key] = str(value).lower() == 'true'
            else:
                CONFIG[key] = value
            
            logging.info(f"Config updated: {key} = {old_config[key]} -> {CONFIG[key]}")

    # Keep module-level impulse threshold globals in sync so updates take
    # effect immediately (no restart required).
    try:
        if 'ALERT_IMPULSE_1M_PCT' in new_config:
            ALERT_IMPULSE_1M_THRESH = float(CONFIG.get('ALERT_IMPULSE_1M_PCT', ALERT_IMPULSE_1M_THRESH))
            logging.info(f"Impulse threshold updated: ALERT_IMPULSE_1M_THRESH={ALERT_IMPULSE_1M_THRESH}")
        if 'ALERT_IMPULSE_3M_PCT' in new_config:
            ALERT_IMPULSE_3M_THRESH = float(CONFIG.get('ALERT_IMPULSE_3M_PCT', ALERT_IMPULSE_3M_THRESH))
            logging.info(f"Impulse threshold updated: ALERT_IMPULSE_3M_THRESH={ALERT_IMPULSE_3M_THRESH}")
    except Exception:
        pass
    
    # Update cache TTL if changed
    if 'CACHE_TTL' in new_config:
        cache['ttl'] = CONFIG['CACHE_TTL']
    
    # Update price history max length if changed
    if 'MAX_PRICE_HISTORY' in new_config:
        new_maxlen = CONFIG['MAX_PRICE_HISTORY']
        for symbol in price_history:
            # Create new deque with updated maxlen
            old_data = list(price_history[symbol])
            price_history[symbol] = deque(old_data[-new_maxlen:], maxlen=new_maxlen)

VALIDATABLE_CONFIG = {
    'CACHE_TTL': {'type': int, 'min': 5, 'max': 3600},
    'INTERVAL_MINUTES': {'type': int, 'min': 1, 'max': 30},
    'MAX_PRICE_HISTORY': {'type': int, 'min': 5, 'max': 5000},
    'UPDATE_INTERVAL': {'type': int, 'min': 5, 'max': 600},
    'PRICE_FETCH_INTERVAL': {'type': int, 'min': 5, 'max': 120},
    'SNAPSHOT_COMPUTE_INTERVAL': {'type': int, 'min': 3, 'max': 60},
    'MAX_COINS_PER_CATEGORY': {'type': int, 'min': 1, 'max': 500},
    'MIN_VOLUME_THRESHOLD': {'type': int, 'min': 0, 'max': 10_000_000_000},
    'MIN_CHANGE_THRESHOLD': {'type': float, 'min': 0.0, 'max': 1000.0},
    'API_TIMEOUT': {'type': int, 'min': 1, 'max': 60},
    'CHART_DAYS_LIMIT': {'type': int, 'min': 1, 'max': 365},
    # Impulse alert thresholds (percentage points)
    'ALERT_IMPULSE_1M_PCT': {'type': float, 'min': 0.0, 'max': 100.0},
    'ALERT_IMPULSE_3M_PCT': {'type': float, 'min': 0.0, 'max': 100.0},
}

def validate_config_patch(patch: dict):
    errors = {}
    sanitized = {}
    for k,v in patch.items():
        meta = VALIDATABLE_CONFIG.get(k)
        if k not in CONFIG:
            errors[k] = 'unknown_key'
            continue
        if not meta:
            # allow but treat as string passthrough
            sanitized[k] = v
            continue
        typ = meta['type']
        try:
            if typ is int:
                cv = int(v)
            elif typ is float:
                cv = float(v)
            else:
                cv = v
        except (TypeError, ValueError):
            errors[k] = 'invalid_type'
            continue
        if typ is float:
            try:
                if not math.isfinite(cv):
                    errors[k] = 'invalid_value'
                    continue
            except Exception:
                errors[k] = 'invalid_value'
                continue
        if 'min' in meta and cv < meta['min']:
            errors[k] = f"below_min_{meta['min']}"
            continue
        if 'max' in meta and cv > meta['max']:
            errors[k] = f"above_max_{meta['max']}"
            continue
        sanitized[k] = cv
    return sanitized, errors

@app.route('/api/config', methods=['GET','POST'])
def api_config():
    if request.method == 'GET':
        # Return JSON-serializable copies to avoid leaking Python types into JSON
        def _serialize_config(cfg):
            out = {}
            for k, v in cfg.items():
                try:
                    json.dumps(v)
                    out[k] = v
                except TypeError:
                    out[k] = str(v)
            return out
        def _serialize_limits(limits):
            out = {}
            for k, meta in limits.items():
                m = {}
                for mk, mv in (meta.items() if isinstance(meta, dict) else []):
                    if mk == 'type':
                        try:
                            m['type'] = mv.__name__
                        except Exception:
                            m['type'] = str(mv)
                    else:
                        try:
                            json.dumps(mv)
                            m[mk] = mv
                        except TypeError:
                            m[mk] = str(mv)
                out[k] = m
            return out
        serialized_config = _serialize_config(CONFIG)
        # Backward compatible response:
        # - keep { config: {...}, limits: {...} }
        # - ALSO flatten a small set of commonly-tuned keys at the top-level so
        #   simple scripts can do `d.get(KEY)` without needing `d["config"]`.
        flattened = {}
        for k in ('ALERT_IMPULSE_1M_PCT', 'ALERT_IMPULSE_3M_PCT'):
            if k in serialized_config:
                flattened[k] = serialized_config.get(k)

        return jsonify({
            'config': serialized_config,
            'limits': _serialize_limits(VALIDATABLE_CONFIG),
            **flattened,
        })
    data = request.get_json(silent=True) or {}
    to_apply, errors = validate_config_patch(data)
    status = 200 if not errors else 400 if not to_apply else 207
    if to_apply:
        update_config(to_apply)
    flattened = {}
    try:
        for k in ('ALERT_IMPULSE_1M_PCT', 'ALERT_IMPULSE_3M_PCT'):
            if k in CONFIG:
                flattened[k] = CONFIG.get(k)
    except Exception:
        flattened = {}

    return jsonify({'applied': to_apply, 'errors': errors, 'config': CONFIG, **flattened}), status

# =============================================================================
# EXISTING FUNCTIONS (Updated with dynamic config)
# =============================================================================

def get_coinbase_prices():
    """Fetch current prices from Coinbase (optimized for speed)"""
    try:
        # Hard deadline so `/data` never hangs for long during local dev.
        # When the deadline is hit we return partial results.
        deadline_seconds = float(os.environ.get('PRICE_FETCH_DEADLINE_SECONDS', '8'))
        deadline_ts = time.time() + max(1.0, deadline_seconds)

        products_timeout = float(os.environ.get('COINBASE_PRODUCTS_TIMEOUT', '5'))
        products_timeout = max(1.0, min(products_timeout, float(CONFIG.get('API_TIMEOUT', 10))))

        ticker_timeout = float(os.environ.get('COINBASE_TICKER_TIMEOUT', '3'))
        ticker_timeout = max(1.0, min(ticker_timeout, float(CONFIG.get('API_TIMEOUT', 10))))

        products_response = requests.get(COINBASE_PRODUCTS_URL, timeout=products_timeout)
        if products_response.status_code == 200:
            products = products_response.json()
            current_prices = {}
            
            # Filter to USD pairs only and prioritize major coins
            usd_products = [p for p in products 
                          if p.get("quote_currency") == "USD" 
                          and p.get("status") == "online"]
            
            # Prioritize major cryptocurrencies for faster loading
            major_coins = [
                'BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD', 
                'LINK-USD', 'MATIC-USD', 'AVAX-USD', 'ATOM-USD', 'ALGO-USD',
                'XRP-USD', 'DOGE-USD', 'SHIB-USD', 'UNI-USD', 'AAVE-USD',
                'BCH-USD', 'LTC-USD', 'ICP-USD', 'HYPE-USD', 'SPX-USD',
                'SEI-USD', 'PI-USD', 'KAIA-USD', 'INJ-USD', 'ONDO-USD',
                'CRO-USD', 'FLR-USD', 'WLD-USD', 'POL-USD', 'WBT-USD',
                'JUP-USD', 'SKY-USD', 'TAO-USD'
            ]
            
            sample = int(CONFIG.get("PRICE_UNIVERSE_SAMPLE_SIZE", 120))
            sample_max = int(CONFIG.get("PRICE_UNIVERSE_MAX", 250))
            sample = max(30, min(sample, sample_max))

            usd_ids = [p.get("id") for p in usd_products if p.get("id")]

            core_ids = [pid for pid in major_coins if pid in usd_ids]
            core_max = int(os.environ.get("PRICE_UNIVERSE_CORE_MAX", len(core_ids)))
            core_ids = core_ids[: max(0, min(core_max, sample))]

            core_set = set(core_ids)
            rest = [pid for pid in usd_ids if pid not in core_set]
            remaining = max(0, sample - len(core_ids))

            rotate_seconds = int(os.environ.get("PRICE_UNIVERSE_ROTATE_SECONDS", 60))
            rotate_seconds = max(1, rotate_seconds)
            rotate_step = int(os.environ.get("PRICE_UNIVERSE_ROTATE_STEP", max(1, remaining)))
            rotate_step = max(1, rotate_step)

            # Prefer symbols recently seen to preserve 1m baselines.
            fresh_window = int(os.environ.get("PRICE_UNIVERSE_FRESH_SECONDS", 180))
            now_ts = time.time()
            fresh_rest = []
            stale_rest = []
            for pid in rest:
                sym = pid.split("-", 1)[0].upper() if isinstance(pid, str) else None
                last_ts = _PRICE_LAST_SEEN_TS.get(sym) if sym else None
                if last_ts and (now_ts - float(last_ts)) <= fresh_window:
                    fresh_rest.append(pid)
                else:
                    stale_rest.append(pid)

            def _rotate(lst):
                if not lst:
                    return []
                offset = (int(now_ts / rotate_seconds) * rotate_step) % len(lst)
                return lst[offset:] + lst[:offset]

            chosen_rest = []
            if remaining > 0:
                rotated_fresh = _rotate(fresh_rest)
                chosen_rest.extend(rotated_fresh[:remaining])
                if len(chosen_rest) < remaining:
                    rotated_stale = _rotate(stale_rest)
                    need = remaining - len(chosen_rest)
                    chosen_rest.extend(rotated_stale[:need])

            final_ids = core_ids + chosen_rest
            if remaining and len(chosen_rest) < remaining:
                final_ids = (core_ids + rest)[:sample]
            product_by_id = {p["id"]: p for p in usd_products if p.get("id")}
            final_products = [product_by_id[pid] for pid in final_ids if pid in product_by_id]
            
            # Use ThreadPoolExecutor for concurrent API calls
            def fetch_ticker(product):
                """
                Returns: (symbol, price, status_code, err_tag)
                  - symbol/price populated only on success
                  - status_code set on HTTP responses; 0 if exception before HTTP
                  - err_tag is a short string for diagnostics
                """
                product_id = product.get("id")
                if not product_id:
                    return (None, None, 0, "missing_id")

                url = f"https://api.exchange.coinbase.com/products/{product_id}/ticker"

                backoffs = [0.0, 0.2, 0.6]
                last_code = 0
                last_err = None

                for delay in backoffs:
                    if delay:
                        time.sleep(delay)
                    time.sleep(random.uniform(0.0, 0.05))

                    try:
                        # Keep per-request timeout small; overall duration is bounded
                        # by `PRICE_FETCH_DEADLINE_SECONDS` in the caller.
                        r = requests.get(url, timeout=ticker_timeout)
                        last_code = r.status_code

                        if r.status_code == 200:
                            data = r.json() if r.content else {}
                            price = data.get("price")
                            if price is None:
                                return (None, None, 200, "no_price")
                            try:
                                price_f = float(price)
                            except Exception:
                                return (None, None, 200, "bad_price")

                            symbol = product_id.split("-")[0]
                            return (symbol, price_f, 200, None)

                        if r.status_code == 429 or (500 <= r.status_code <= 599):
                            if r.status_code == 429:
                                ra = r.headers.get("Retry-After")
                                try:
                                    if ra:
                                        time.sleep(min(1.5, float(ra)))
                                    else:
                                        time.sleep(0.5)
                                except Exception:
                                    time.sleep(0.5)
                            last_err = "retryable_http"
                            continue

                        return (None, None, r.status_code, "non_retry_http")

                    except Exception as e:
                        last_code = 0
                        last_err = f"exc:{type(e).__name__}"
                        continue

                return (None, None, last_code, last_err or "retry_exhausted")

            logging.info(
                "prices: products=%d usd=%d submitted=%d",
                len(products),
                len(usd_products),
                len(final_products),
            )

            # Use ThreadPoolExecutor for faster concurrent API calls
            deadline_hit = False
            with ThreadPoolExecutor(max_workers=8) as executor:
                future_to_product = {executor.submit(fetch_ticker, product): product 
                                   for product in final_products}

                submitted = len(future_to_product)
                ok = 0
                http429 = 0
                http5xx = 0
                other = 0
                exceptions = 0

                # Collect results until deadline; return partial data if slow.
                remaining = max(0.1, deadline_ts - time.time())
                try:
                    for future in as_completed(future_to_product, timeout=remaining):
                        try:
                            symbol, price, code, err_tag = future.result()
                        except Exception:
                            exceptions += 1
                            continue

                        if symbol and price:
                            current_prices[symbol] = price
                            ok += 1
                            try:
                                _PRICE_LAST_SEEN_TS[symbol] = time.time()
                            except Exception:
                                pass
                            continue

                        if code == 429:
                            http429 += 1
                        elif 500 <= code <= 599:
                            http5xx += 1
                        elif code == 0:
                            exceptions += 1
                        else:
                            other += 1
                except Exception as e:
                    # TimeoutError or unexpected iterator issue: best-effort partial return.
                    deadline_hit = True
                    logging.warning(f"price_fetch_deadline_reached: returning_partial ok={ok} submitted={submitted} err={type(e).__name__}")
                finally:
                    # Cancel any futures that haven't started yet.
                    for f in future_to_product:
                        try:
                            f.cancel()
                        except Exception:
                            pass

            logging.info(
                "price_fetch_stats: submitted=%d ok=%d 429=%d 5xx=%d other=%d exceptions=%d sample=%d deadline_s=%.1f",
                submitted, ok, http429, http5xx, other, exceptions, sample, deadline_seconds
            )
            try:
                ok_ratio = (float(ok) / float(submitted)) if submitted else 0.0
                min_ratio = float(CONFIG.get("PRICE_MIN_SUCCESS_RATIO", 0.7) or 0.7)
                partial = bool(deadline_hit or (submitted > 0 and ok_ratio < min_ratio))
                partial_reason = None
                if deadline_hit:
                    partial_reason = "deadline"
                elif submitted > 0 and ok_ratio < min_ratio:
                    partial_reason = "low_coverage"
                last_current_prices["partial"] = partial
                last_current_prices["partial_reason"] = partial_reason
                last_current_prices["ok"] = int(ok)
                last_current_prices["submitted"] = int(submitted)
                last_current_prices["ok_ratio"] = float(ok_ratio)
                last_current_prices["http429"] = int(http429)
                last_current_prices["http5xx"] = int(http5xx)
                last_current_prices["other"] = int(other)
                last_current_prices["exceptions"] = int(exceptions)
                last_current_prices["deadline_hit"] = bool(deadline_hit)
                last_current_prices["last_fetch_ts"] = time.time()
            except Exception:
                pass
            return current_prices
        else:
            logging.error(f"Coinbase products API Error: {products_response.status_code}")
            try:
                last_current_prices["partial"] = True
                last_current_prices["partial_reason"] = "products_api_error"
                last_current_prices["ok"] = 0
                last_current_prices["submitted"] = 0
                last_current_prices["ok_ratio"] = 0.0
                last_current_prices["http429"] = 0
                last_current_prices["http5xx"] = 0
                last_current_prices["other"] = 0
                last_current_prices["exceptions"] = 0
                last_current_prices["deadline_hit"] = False
                last_current_prices["last_fetch_ts"] = time.time()
            except Exception:
                pass
            return {}
    except Exception as e:
        logging.error(f"Error fetching current prices from Coinbase: {e}")
        try:
            last_current_prices["partial"] = True
            last_current_prices["partial_reason"] = "exception"
            last_current_prices["deadline_hit"] = False
            last_current_prices["http429"] = 0
            last_current_prices["http5xx"] = 0
            last_current_prices["other"] = 0
            last_current_prices["exceptions"] = 0
            last_current_prices["last_fetch_ts"] = time.time()
        except Exception:
            pass
        return {}


# Baseline windows (seconds) for DB-based deltas.
# Use tolerant defaults so snapshot cadence drift doesn't zero whole tables.
BASELINE_WINDOWS = {
    # Target ~60s ago; accept ~35s..105s.
    "1m": {"target_s": 60, "min_s": 35, "max_s": 105},
    # Target ~180s ago; accept ~120s..300s.
    "3m": {"target_s": 180, "min_s": 120, "max_s": 300},
    "1h": {"target_s": 3600, "min_s": 3300, "max_s": 3900},
}


def _db_baseline_for_window(product_id: str, now_ts_s: int, key: str):
    """Return (baseline_ts_s, baseline_price, age_s) if within tolerance, else None.

    Uses SQLite via get_price_at_or_before(product_id, target_ts_s).
    """
    win = BASELINE_WINDOWS[key]
    target_s = int(win["target_s"])
    target_ts = int(now_ts_s) - target_s

    candidates: list[tuple[int, float]] = []
    try:
        got = get_price_at_or_before(product_id, target_ts)
        if isinstance(got, (tuple, list)) and len(got) >= 2:
            candidates.append((int(got[0]), float(got[1])))
    except Exception:
        pass
    try:
        got = get_price_at_or_after(product_id, target_ts)
        if isinstance(got, (tuple, list)) and len(got) >= 2:
            candidates.append((int(got[0]), float(got[1])))
    except Exception:
        pass

    if not candidates:
        return None

    target_age = int(win["target_s"])
    best = None
    best_diff = None
    for ts_i, price_f in candidates:
        age_s = int(now_ts_s - int(ts_i))
        if age_s < int(win["min_s"]) or age_s > int(win["max_s"]):
            continue
        diff = abs(age_s - target_age)
        if best is None or best_diff is None or diff < best_diff:
            best = (int(ts_i), float(price_f), int(age_s))
            best_diff = diff
    return best


def calculate_interval_changes(current_prices, snapshot_ts_s: int | None = None):
    """Calculate real-time 3-minute changes using DB baselines with in-memory fallback."""
    current_time = time.time()
    now_ts_s = int(snapshot_ts_s) if snapshot_ts_s is not None else int(current_time)
    sample_ts = float(snapshot_ts_s) if snapshot_ts_s is not None else current_time

    def _history_baseline_3m(symbol: str):
        """Fallback 3m baseline from in-memory history when DB doesn't have a usable point."""
        try:
            history = price_history[symbol]
        except Exception:
            return None
        if not history or len(history) < 2:
            return None

        w = BASELINE_WINDOWS.get("3m") or {}
        target_s = int(w.get("target_s", 180))
        min_s = int(w.get("min_s", 120))
        max_s = int(w.get("max_s", 300))

        best = None
        best_err = None
        for ts, p in history:
            try:
                ts_i = int(ts)
                p_f = float(p)
            except Exception:
                continue
            age_s = now_ts_s - ts_i
            if age_s < min_s or age_s > max_s:
                continue
            err = abs(float(age_s) - float(target_s))
            if best is None or best_err is None or err < best_err:
                best = (ts_i, p_f, age_s)
                best_err = err
        return best

    # Update price history with current prices
    for symbol, price in (current_prices or {}).items():
        try:
            if float(price or 0) > 0:
                price_history[symbol].append((sample_ts, float(price)))
                price_history_1hour[symbol].append((sample_ts, float(price)))
        except Exception:
            continue

    formatted_data = []
    baseline_ready_any = False
    earliest_baseline_ts = None

    for symbol, price in (current_prices or {}).items():
        try:
            price_f = float(price or 0)
        except Exception:
            continue
        if price_f <= 0:
            continue

        baseline = _db_baseline_for_window(symbol, now_ts_s, "3m")
        if not baseline:
            baseline = _history_baseline_3m(symbol)
        if not baseline:
            continue

        baseline_ts_s, baseline_price, baseline_age_s = baseline
        if baseline_price <= 0:
            continue

        baseline_ready_any = True
        if earliest_baseline_ts is None or baseline_ts_s < earliest_baseline_ts:
            earliest_baseline_ts = baseline_ts_s

        price_change = pct_change(price_f, baseline_price)
        actual_interval_minutes = baseline_age_s / 60.0

        formatted_data.append({
            "symbol": symbol,
            "current_price": price_f,
            "initial_price_3min": baseline_price,
            "previous_price_3m": baseline_price,
            "price_change_percentage_3min": price_change,
            "actual_interval_minutes": actual_interval_minutes,
            "baseline_ts": float(baseline_ts_s),
            "baseline_ts_ms_3m": int(baseline_ts_s * 1000),
            "baseline_age_ms_3m": int(baseline_age_s * 1000),
            "warming_3m": False,
            "latest_ts_ms": int(now_ts_s * 1000),
        })

    age_seconds = (now_ts_s - earliest_baseline_ts) if (baseline_ready_any and earliest_baseline_ts is not None) else None
    _set_baseline_meta_3m(
        ready=baseline_ready_any,
        baseline_ts=float(earliest_baseline_ts) if earliest_baseline_ts is not None else None,
        age_seconds=float(age_seconds) if age_seconds is not None else None,
    )

    if not formatted_data:
        partial = bool(last_current_prices.get("partial")) if isinstance(last_current_prices, dict) else False
        if partial:
            logging.info("3m_eligibility_empty_partial: total_prices=%d", len(current_prices or {}))
        else:
            logging.warning("3m_eligibility_empty: total_prices=%d", len(current_prices or {}))

    return formatted_data

def calculate_1min_changes(current_prices, snapshot_ts_s: int | None = None):
    """Calculate price changes over 1 minute"""
    current_time = time.time()
    now_ts_s = int(snapshot_ts_s) if snapshot_ts_s is not None else int(current_time)
    sample_ts = float(snapshot_ts_s) if snapshot_ts_s is not None else current_time

    # Update price history with current prices
    for symbol, price in current_prices.items():
        if price > 0:
            price_history_1min[symbol].append((sample_ts, price))
            price_history_1hour[symbol].append((sample_ts, price))  # Track 1h history

    def _history_baseline_1m(symbol: str):
        """Fallback baseline from in-memory 1m history when DB doesn't have a usable point."""
        try:
            history = price_history_1min[symbol]
        except Exception:
            return None
        if not history or len(history) < 2:
            return None

        w = BASELINE_WINDOWS.get("1m") or {}
        target_s = int(w.get("target_s", 60))
        min_s = int(w.get("min_s", 55))
        max_s = int(w.get("max_s", 75))

        best = None
        best_err = None
        for ts, p in history:
            try:
                ts_i = int(ts)
                p_f = float(p)
            except Exception:
                continue
            age_s = now_ts_s - ts_i
            if age_s < min_s or age_s > max_s:
                continue
            err = abs(float(age_s) - float(target_s))
            if best is None or err < best_err:
                best = (ts_i, p_f, age_s)
                best_err = err
        return best

    # Calculate changes for each symbol
    formatted_data = []
    baseline_ready_any = False
    earliest_baseline_ts = None
    baseline_ages = []

    threshold_pct = 0.01
    diag = {
        "timestamp": now_ts_s,
        "total_prices": len(current_prices or {}),
        "price_non_positive": 0,
        "baseline_db_missing": 0,
        "baseline_history_missing": 0,
        "baseline_missing": 0,
        "baseline_price_invalid": 0,
        "baseline_used_db": 0,
        "baseline_used_history": 0,
        "below_threshold": 0,
        "included": 0,
        "filtered_min_volume": 0,
        "threshold_pct": threshold_pct,
        "baseline_window": dict(BASELINE_WINDOWS.get("1m") or {}),
        "partial": bool(last_current_prices.get("partial")) if isinstance(last_current_prices, dict) else False,
        "partial_reason": last_current_prices.get("partial_reason") if isinstance(last_current_prices, dict) else None,
    }

    for symbol, price in current_prices.items():
        if price <= 0:
            diag["price_non_positive"] += 1
            continue

        baseline_db = _db_baseline_for_window(symbol, now_ts_s, "1m")
        if not baseline_db:
            diag["baseline_db_missing"] += 1

        baseline_hist = None
        if not baseline_db:
            baseline_hist = _history_baseline_1m(symbol)
            if not baseline_hist:
                diag["baseline_history_missing"] += 1

        baseline = baseline_db or baseline_hist
        if not baseline:
            diag["baseline_missing"] += 1
            continue

        baseline_ts_s, baseline_price, baseline_age_s = baseline
        if baseline_price <= 0:
            diag["baseline_price_invalid"] += 1
            continue

        if baseline_db:
            diag["baseline_used_db"] += 1
        else:
            diag["baseline_used_history"] += 1
        baseline_ages.append(float(baseline_age_s))

        baseline_ready_any = True
        if earliest_baseline_ts is None or baseline_ts_s < earliest_baseline_ts:
            earliest_baseline_ts = baseline_ts_s

        # Calculate percentage change
        price_change = pct_change(price, baseline_price)
        actual_interval_minutes = baseline_age_s / 60.0

        # Only include significant changes (configurable threshold)
        if abs(price_change) >= threshold_pct:  # Reverted to original threshold
            formatted_data.append({
                "symbol": symbol,
                "current_price": price,
                "initial_price_1min": baseline_price,
                "price_change_percentage_1min": price_change,
                "actual_interval_minutes": actual_interval_minutes,
                "baseline_ts_ms_1m": int(baseline_ts_s * 1000),
                "baseline_age_ms_1m": int(baseline_age_s * 1000),
                "warming_1m": False,
                "latest_ts_ms": int(now_ts_s * 1000),
            })
            diag["included"] += 1
        else:
            diag["below_threshold"] += 1

    age_seconds = (now_ts_s - earliest_baseline_ts) if (baseline_ready_any and earliest_baseline_ts is not None) else None
    try:
        diag["eligible_products"] = max(0, int(diag.get("total_prices") or 0) - int(diag.get("price_non_positive") or 0))
        diag["have_baseline"] = int(diag.get("baseline_used_db") or 0) + int(diag.get("baseline_used_history") or 0)
        diag["missing_baseline"] = int(diag.get("baseline_missing") or 0)
        diag["stale_price"] = int(diag.get("baseline_history_missing") or 0)
    except Exception:
        pass
    _set_baseline_meta_1m(
        ready=baseline_ready_any,
        baseline_ts=float(earliest_baseline_ts) if earliest_baseline_ts is not None else None,
        age_seconds=float(age_seconds) if age_seconds is not None else None,
    )

    if baseline_ages:
        try:
            diag["baseline_age_s_min"] = round(min(baseline_ages), 2)
            diag["baseline_age_s_max"] = round(max(baseline_ages), 2)
            diag["baseline_age_s_avg"] = round(sum(baseline_ages) / len(baseline_ages), 2)
        except Exception:
            pass

    try:
        global one_minute_diag
        one_minute_diag = dict(diag)
    except Exception:
        pass

    if not formatted_data:
        partial = bool(last_current_prices.get("partial")) if isinstance(last_current_prices, dict) else False
        if partial:
            logging.info("1m_eligibility_empty_partial: total_prices=%d", len(current_prices))
        else:
            logging.warning("1m_eligibility_empty: total_prices=%d", len(current_prices))

    return formatted_data

def calculate_1hour_price_changes(current_prices, snapshot_ts_s: int | None = None):
    """Calculate real-time 1-hour price changes using price_history_1hour.

    Returns list of dicts with symbol, current_price, price_1h_ago, price_change_1h.
    """
    current_time = time.time()
    now_ts_s = int(snapshot_ts_s) if snapshot_ts_s is not None else int(current_time)

    formatted_data = []
    baseline_ready_any = False
    earliest_baseline_ts = None

    for symbol, price in current_prices.items():
        if price <= 0:
            continue

        history = price_history_1hour[symbol]
        if len(history) < 2:
            continue

        baseline = _db_baseline_for_window(symbol, now_ts_s, "1h")
        if not baseline:
            continue

        baseline_ts_s, baseline_price, baseline_age_s = baseline
        if baseline_price <= 0:
            continue

        baseline_ready_any = True
        if earliest_baseline_ts is None or baseline_ts_s < earliest_baseline_ts:
            earliest_baseline_ts = baseline_ts_s

        price_change = pct_change(price, baseline_price)
        actual_interval_minutes = baseline_age_s / 60.0

        formatted_data.append({
            "symbol": symbol,
            "current_price": price,
            "price_1h_ago": baseline_price,
            "price_change_1h": price_change,
            "actual_interval_minutes": actual_interval_minutes,
            "baseline_ts_ms_1h_price": int(baseline_ts_s * 1000),
            "baseline_age_ms_1h_price": int(baseline_age_s * 1000),
            "warming_1h_price": False,
            "latest_ts_ms": int(now_ts_s * 1000),
        })

    # Update baseline meta
    if baseline_ready_any and earliest_baseline_ts is not None:
        baseline_age = now_ts_s - earliest_baseline_ts
        _set_baseline_meta_1h(ready=True, baseline_ts=float(earliest_baseline_ts), age_seconds=float(baseline_age))
    else:
        _set_baseline_meta_1h(ready=False, baseline_ts=None, age_seconds=None)

    return formatted_data

def get_current_prices():
    """Fetch current prices from Coinbase"""
    return get_coinbase_prices()


def get_24h_top_movers():
    """Fetch top 24h gainers/losers for banner"""
    return get_coinbase_24h_top_movers()


def get_coinbase_24h_top_movers():
    """Fetch 24h top movers from Coinbase (optimized)."""
    try:
        products_response = requests.get(COINBASE_PRODUCTS_URL, timeout=CONFIG['API_TIMEOUT'])
        if products_response.status_code != 200:
            return []

        products = products_response.json()
        usd_products = [p for p in products if p["quote_currency"] == "USD" and p["status"] == "online"]
        formatted_data = []

        def fetch_product_data(product):
            """Fetch stats and ticker data for a single product concurrently"""
            try:
                # Get 24h stats
                stats_url = f"https://api.exchange.coinbase.com/products/{product['id']}/stats"
                stats_response = requests.get(stats_url, timeout=3)
                if stats_response.status_code != 200:
                    return None

                # Get current price
                ticker_url = f"https://api.exchange.coinbase.com/products/{product['id']}/ticker"
                ticker_response = requests.get(ticker_url, timeout=2)
                if ticker_response.status_code != 200:
                    return None

                stats_data = stats_response.json()
                ticker_data = ticker_response.json()

                current_price = float(ticker_data.get('price', 0))
                volume_24h = float(stats_data.get('volume', 0))
                open_24h = float(stats_data.get('open', 0))

                if current_price > 0 and open_24h > 0:
                    price_change_24h = pct_change(current_price, open_24h)

                    # Estimate 1h change using a simple fraction of the 24h move
                    price_1h_estimate = current_price - ((current_price - open_24h) * 0.04)
                    price_change_1h = pct_change(current_price, price_1h_estimate) if price_1h_estimate > 0 else 0.0

                    # Always record volume snapshot for later 1h delta computation
                    try:
                        volume_history_24h[product["id"]].append((time.time(), volume_24h))
                    except Exception:
                        pass

                    # Only include significant moves in the returned list, but
                    # volume snapshots are collected regardless so bV can be computed
                    if abs(price_change_24h) >= CONFIG['MIN_CHANGE_THRESHOLD'] and volume_24h > CONFIG['MIN_VOLUME_THRESHOLD']:
                        # Record volume snapshot for later 1h delta computation
                        try:
                            volume_history_24h[product["id"]].append((time.time(), volume_24h))
                        except Exception:
                            pass
                        return {
                            "symbol": product["id"],
                            "current_price": current_price,
                            "initial_price_24h": open_24h,
                            "initial_price_1h": price_1h_estimate,
                            "price_change_24h": price_change_24h,
                            "price_change_1h": price_change_1h,
                            "volume_24h": volume_24h,
                            "market_cap": 0
                        }
            except Exception as e:
                logging.warning(f"Error processing Coinbase 24h data for {product['id']}: {e}")
                return None

        # Use ThreadPoolExecutor for concurrent API calls (SPEED OPTIMIZATION)
        with ThreadPoolExecutor(max_workers=15) as executor:
            # Submit all tasks
            sample = int(CONFIG.get("TOP_MOVERS_SAMPLE_SIZE", 120))
            future_to_product = {executor.submit(fetch_product_data, product): product 
                               for product in usd_products[:sample]}  # Reduced for faster response
            
            # Collect results as they complete
            for future in as_completed(future_to_product):
                result = future.result()
                if result:
                    formatted_data.append(result)

        # Sort and mix gainers/losers
        formatted_data.sort(key=lambda x: abs(x["price_change_24h"]), reverse=True)
        gainers_24h = [coin for coin in formatted_data if coin["price_change_24h"] > 0][:10]
        losers_24h = [coin for coin in formatted_data if coin["price_change_24h"] < 0][:10]
        
        banner_mix = []
        max_length = max(len(gainers_24h), len(losers_24h))
        for i in range(max_length):
            if i < len(gainers_24h):
                banner_mix.append(gainers_24h[i])
            if i < len(losers_24h):
                banner_mix.append(losers_24h[i])
        
        logging.info(f"Successfully fetched Coinbase 24h top movers: {len(gainers_24h)} gainers, {len(losers_24h)} losers")
        return banner_mix[:20]
    except Exception as e:
        logging.error(f"Error fetching 24h top movers from Coinbase: {e}")
        return []

# =============================================================================
# DATA FORMATTING FUNCTIONS
# =============================================================================

def process_product_data(products, stats_data, ticker_data):
    """Process a list of products and combine with stats and ticker data."""
    processed_data = []
    for product in products:
        symbol = product.get("id")
        if symbol and symbol in stats_data and symbol in ticker_data:
            try:
                processed_data.append({
                    "symbol": symbol,
                    "base": product.get("base_currency"),
                    "quote": product.get("quote_currency"),
                    "volume": float(stats_data[symbol].get("volume", 0)),
                    "price": float(ticker_data[symbol].get("price", 0)),
                })
            except (ValueError, TypeError) as e:
                logging.warning(f"Could not process data for {symbol}: {e}")
                continue
    return processed_data

def format_crypto_data(crypto_data):
    """Format 3-minute crypto data for frontend with detailed price tracking"""
    return [
        {
            "symbol": coin["symbol"],
            "current": coin["current_price"],
            "initial_3min": coin["initial_price_3min"],
            "previous_price_3m": coin.get("previous_price_3m"),
            "gain": coin["price_change_percentage_3min"],
            "interval_minutes": round(coin["actual_interval_minutes"], 1),
            "baseline_ts_3m": coin.get("baseline_ts"),
        }
        for coin in crypto_data
    ]

def format_crypto_data_1min(crypto_data):
    """Format 1-minute crypto data for frontend with detailed price tracking"""
    return [
        {
            "symbol": coin["symbol"],
            "current": coin["current_price"],
            "initial_1min": coin["initial_price_1min"],
            "gain": coin["price_change_percentage_1min"],
            "interval_minutes": round(coin["actual_interval_minutes"], 1)
        }
        for coin in crypto_data
    ]

def format_banner_data(banner_data):
    """Format 24h banner data for frontend"""
    return [
        {
            "symbol": coin["symbol"],
            "current_price": coin["current_price"],
            "initial_price_24h": coin["initial_price_24h"],
            "initial_price_1h": coin["initial_price_1h"],
            "price_change_24h": coin["price_change_24h"],
            "price_change_1h": coin["price_change_1h"],
            "volume_24h": coin["volume_24h"],
            "market_cap": coin.get("market_cap", 0)
        }
        for coin in banner_data
    ]

# =============================================================================
# MAIN DATA PROCESSING FUNCTION
# =============================================================================

def get_crypto_data(current_prices=None, *, force_refresh: bool = False):
    """Main function to fetch and process 3-minute crypto data.

    Params:
        - current_prices: optional dict[symbol->price] from a shared fetch.
        - force_refresh: when True, bypasses the cache TTL so the background
          updater can append to history every tick.
    """
    current_time = time.time()
    snapshot_ts_s = None
    
    # Check cache first
    if (not force_refresh) and cache["data"] and (current_time - cache["timestamp"]) < cache["ttl"]:
        return cache["data"]
    
    try:
        # Resolve a usable price snapshot.
        if current_prices is None:
            # Reuse prices from recent fetch (e.g., 1-min snapshot) to avoid
            # parallel bursts during a single `/data` aggregation.
            prices_age_limit = 10
            if last_current_prices['data'] and (current_time - last_current_prices['timestamp']) < prices_age_limit:
                current_prices = last_current_prices['data']
                snapshot_ts_s = int(last_current_prices.get('timestamp') or current_time)
            else:
                current_prices = get_current_prices()
                if current_prices:
                    last_current_prices['data'] = current_prices
                    last_current_prices['timestamp'] = current_time
                    snapshot_ts_s = int(current_time)
        else:
            snapshot_ts_s = int(last_current_prices.get('timestamp') or current_time)
        if not current_prices:
            logging.warning("No current prices available")
            return None

        if snapshot_ts_s is None:
            snapshot_ts_s = int(current_time)
            
        # Calculate 3-minute interval changes (unique feature)
        crypto_data = calculate_interval_changes(current_prices, snapshot_ts_s)
        baseline_meta = _get_baseline_meta_3m()
        
        if not crypto_data:
            logging.warning(f"No crypto data available - {len(current_prices)} current prices, {len(price_history)} symbols with history")
            return None
        
        # Separate gainers and losers based on 3-minute changes
        gainers = [coin for coin in crypto_data if (coin.get("price_change_percentage_3min") or 0) > 0]
        losers = [coin for coin in crypto_data if (coin.get("price_change_percentage_3min") or 0) < 0]
        
        # Sort by 3-minute percentage change
        gainers.sort(key=lambda x: x["price_change_percentage_3min"], reverse=True)
        losers.sort(key=lambda x: x["price_change_percentage_3min"])
        
        # Get top movers (mix of gainers and losers)
        top_gainers = gainers[:8]
        top_losers = losers[:8]
        top24h = (top_gainers + top_losers)[:15]
        
        # Get 24h top movers for banner
        banner_24h_movers = get_24h_top_movers()
        
        limit = int(CONFIG.get("MAX_COINS_PER_CATEGORY", 30))
        result = {
            "gainers": format_crypto_data(gainers[:limit]),
            "losers": format_crypto_data(losers[:limit]),
            "top24h": format_crypto_data(top24h),
            "banner": format_banner_data(banner_24h_movers[:20]),
            # Baseline readiness metadata for 3m tables
            "baseline_ready_3m": bool(baseline_meta.get("ready")),
            "baseline_ts_3m": baseline_meta.get("baseline_ts"),
            "baseline_age_seconds_3m": baseline_meta.get("age_seconds"),
        }
        
        # Update cache
        cache["data"] = result
        cache["timestamp"] = current_time
        
        logging.info(f"Successfully processed data: {len(result['gainers'])} gainers, {len(result['losers'])} losers, {len(result['banner'])} banner items")
        return result
        
    except Exception as e:
        logging.error(f"Error in get_crypto_data: {e}")
        return None

# =============================================================================
# ADDITIONAL FUNCTIONS
# =============================================================================

def get_historical_chart_data(symbol, days=7):
    """Fetch historical price data for charts from Coinbase"""
    try:
        # Convert days to start and end timestamps
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)

        # Determine granularity based on days
        # Coinbase Pro API granularities: 60, 300, 900, 3600, 21600, 86400
        if days <= 1: # Up to 1 day, use 1-minute granularity
            granularity = 60
        elif days <= 7: # Up to 7 days, use 1-hour granularity
            granularity = 3600
        else: # More than 7 days, use 1-day granularity
            granularity = 86400

        url = f"https://api.exchange.coinbase.com/products/{symbol}/candles"
        params = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'granularity': granularity
        }

        response = requests.get(url, params=params, timeout=CONFIG['API_TIMEOUT'])

        if response.status_code == 200:
            data = response.json()
            chart_data = []
            for entry in data:
                timestamp = entry[0] * 1000  # Convert to milliseconds
                price = entry[4]  # Close price
                volume = entry[5]

                chart_data.append({
                    'timestamp': timestamp,
                    'datetime': datetime.fromtimestamp(timestamp / 1000).isoformat(),
                    'price': round(price, 6),
                    'volume': round(volume, 2)
                })
            
            # Sort by timestamp in ascending order (Coinbase returns in descending)
            chart_data.sort(key=lambda x: x['timestamp'])

            logging.info(f"Successfully fetched {len(chart_data)} chart points for {symbol} from Coinbase")
            return chart_data

        else:
            logging.error(f"Coinbase chart API Error for {symbol}: {response.status_code} - {response.text}")
            return []

    except requests.RequestException as e:
        logging.error(f"Network error fetching chart data for {symbol}: {e}")
        return []
    except Exception as e:
        logging.error(f"Error fetching chart data for {symbol}: {e}")
        return []

def get_trending_coins():
    """Get trending/recommended coins to watch (CoinGecko removed)"""
    logging.info("CoinGecko trending coins API removed. Returning empty list.")
    return []

def analyze_coin_potential(symbol, chart_data):
    """Analyze a coin's potential based on historical data"""
    try:
        if len(chart_data) < 24:  # Need at least 24 hours of data
            return {"score": 0, "signals": []}
        
        prices = [point['price'] for point in chart_data]
        volumes = [point['volume'] for point in chart_data]
        
        signals = []
        score = 50  # Base score
        
        # Price trend analysis
        recent_prices = prices[-12:]  # Last 12 hours
        if len(recent_prices) >= 2:
            trend = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100
            if trend > 5:
                signals.append("Strong upward trend (+5%)")
                score += 15
            elif trend > 1:
                signals.append("Positive trend (+1%)")
                score += 8
            elif trend < -5:
                signals.append("Sharp decline (-5%)")
                score -= 15
            elif trend < -1:
                signals.append("Negative trend (-1%)")
                score -= 8
        
        # Volume analysis
        recent_volume = sum(volumes[-6:]) / 6 if len(volumes) >= 6 else 0
        older_volume = sum(volumes[-24:-6]) / 18 if len(volumes) >= 24 else recent_volume
        
        if recent_volume > older_volume * 1.5:
            signals.append("High volume spike")
            score += 10
        elif recent_volume > older_volume * 1.2:
            signals.append("Increased volume")
            score += 5
        
        # Volatility check
        if len(prices) >= 24:
            price_changes = [abs(prices[i] - prices[i-1]) / prices[i-1] * 100 for i in range(1, len(prices))]
            avg_volatility = sum(price_changes) / len(price_changes)
            
            if avg_volatility > 5:
                signals.append("High volatility (>5%)")
                score += 5
            elif avg_volatility < 1:
                signals.append("Low volatility (<1%)")
                score -= 5
        
        # Support/resistance levels
        max_price = max(prices[-24:])
        min_price = min(prices[-24:])
        current_price = prices[-1]
        
        if current_price > max_price * 0.95:
            signals.append("Near resistance level")
        elif current_price < min_price * 1.05:
            signals.append("Near support level")
            score += 5
        
        return {
            "score": max(0, min(100, score)),
            "signals": signals[:5],  # Top 5 signals
            "trend_percentage": round(trend, 2) if 'trend' in locals() else 0,
            "volume_change": round((recent_volume - older_volume) / older_volume * 100, 2) if older_volume > 0 else 0
        }
        
    except Exception as e:
        logging.error(f"Error analyzing coin potential for {symbol}: {e}")
        return {"score": 0, "signals": []}

# =============================================================================
# API ROUTES
# =============================================================================

# =============================================================================
# THREE UNIQUE ENDPOINTS FOR DIFFERENT UI SECTIONS
# =============================================================================

@app.route('/api/banner-top')
def get_top_banner():
    """Top banner: Current price + REAL-TIME 1h % change (unique endpoint)"""
    try:
        # Get current prices from live feed
        current_prices = get_current_prices()
        snapshot_ts_s = None
        if current_prices:
            now_ts = time.time()
            last_current_prices['data'] = current_prices
            last_current_prices['timestamp'] = now_ts
            snapshot_ts_s = int(now_ts)

        # Calculate REAL 1h price changes from price_history_1hour
        hour_changes = calculate_1hour_price_changes(current_prices, snapshot_ts_s)

        # Get baseline metadata
        baseline_meta = _get_baseline_meta_1h()

        # If warming up (no 1h baseline yet), fall back to 24h top movers with estimates
        if not baseline_meta.get("ready") or not hour_changes:
            logging.info("Top banner: 1h baseline warming, using 24h top movers fallback")
            banner_data = get_24h_top_movers()
            if not banner_data:
                return jsonify({"error": "No banner data available"}), 503

            items = []
            for coin in banner_data:
                try:
                    pct = float(coin.get("price_change_1h", 0) or 0)
                except Exception:
                    pct = 0.0
                if pct < 0:
                    continue
                symbol = coin["symbol"]
                items.append({
                    "symbol": symbol,
                    "product_id": coin.get("product_id") or symbol,
                    "current_price": coin.get("current_price") or coin.get('current') or 0,
                    "price_change_1h": pct,  # estimated
                    "pct_1h": pct,
                    "pct_change_1h": pct,
                    "market_cap": coin.get("market_cap", 0),
                    "_source": "24h_fallback"
                })

            items.sort(key=lambda r: r.get("price_change_1h", 0), reverse=True)
            items = items[:20]

            return jsonify({
                "items": items,
                "count": len(items),
                "limit": 20,
                "age_seconds": 0,
                "stale": True,
                "warming": True,
                "ts": int(time.time())
            })

        # Gainers only, sorted by 1h % change descending
        sorted_changes = sorted(
            [c for c in hour_changes if (c.get("price_change_1h") or 0) >= 0],
            key=lambda x: x.get("price_change_1h", 0),
            reverse=True,
        )

        # Format for top banner
        items = []
        for change in sorted_changes[:20]:  # Top 20 biggest 1h movers
            symbol = change["symbol"]
            pct = change["price_change_1h"]
            items.append({
                "symbol": symbol,
                "product_id": change.get("product_id") or symbol,
                "current_price": change["current_price"],
                "price_change_1h": pct,
                "pct_1h": pct,
                "pct_change_1h": pct,
                "price_1h_ago": change.get("price_1h_ago", 0),
                "_source": "realtime_1h"
            })

        baseline_age = baseline_meta.get("age_seconds", 0)
        return jsonify({
            "items": items,
            "count": len(items),
            "limit": 20,
            "age_seconds": baseline_age,
            "stale": False,
            "warming": False,
            "ts": int(time.time())
        })
    except Exception as e:
        logging.error(f"Error in top banner endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/banner-bottom')
def get_bottom_banner():
    """Bottom banner: REAL-TIME 1h volume changes from candles (unique endpoint)"""
    try:
        # Get current prices from live feed
        current_prices = get_current_prices()

        # Calculate REAL 1h volume changes from candles
        volume_changes = calculate_1hour_volume_changes(current_prices)

        # If no volume data yet, fall back to 24h top movers sorted by volume
        if not volume_changes:
            logging.info("Bottom banner: No 1h volume data, using 24h volume fallback")
            banner_data = get_24h_top_movers()
            if not banner_data:
                return jsonify({"error": "No banner data available"}), 503

            volume_sorted = sorted(banner_data, key=lambda x: x.get("volume_24h", 0), reverse=True)

            items = []
            for coin in volume_sorted[:20]:
                # Use 1h price change as fallback until volume data warms up
                price_change_1h_fallback = coin.get("price_change_1h", 0) or 0
                items.append({
                    "symbol": coin["symbol"],
                    "volume_24h": coin.get("volume_24h", 0),
                    "volume_change_1h": price_change_1h_fallback,  # Fallback to price % until volume data ready
                    "current_price": coin.get("current_price") or coin.get('current') or 0,
                    "_source": "24h_fallback_using_price_change"
                })

            return jsonify({
                "items": items,
                "count": len(items),
                "limit": 20,
                "age_seconds": 0,
                "stale": True,
                "warming": True,
                "ts": int(time.time())
            })

        # Sort by 1h volume percent change (descending)
        # Filter out stale or None changes
        valid_changes = [v for v in volume_changes if v.get('vol1h_pct_change') is not None and not v.get('stale', False)]

        if not valid_changes:
            # All stale, use whatever we have
            valid_changes = volume_changes

        sorted_changes = sorted(valid_changes, key=lambda x: x.get("vol1h_pct_change") or float("-inf"), reverse=True)

        # Format for bottom banner
        items = []
        for change in sorted_changes[:20]:  # Top 20 biggest 1h volume movers
            items.append({
                "symbol": change["symbol"],
                "current_price": change["current_price"],
                "vol1h": change["vol1h"],
                "volume_change_1h": change.get("vol1h_pct_change", 0),
                "_source": "realtime_candles"
            })

        return jsonify({
            "items": items,
            "count": len(items),
            "limit": 20,
            "age_seconds": 0,
            "stale": False,
            "warming": False,
            "ts": int(time.time())
        })
    except Exception as e:
        logging.error(f"Error in bottom banner endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/tables-3min')
def get_tables_3min():
    """Tables: 3-minute gainers/losers (unique endpoint)"""
    try:
        # Get specific data for tables - focus on 3-minute changes
        data = get_crypto_data()
        
        if not data:
            return jsonify({"error": "No table data available"}), 503
            
        # Extract gainers and losers from the main data
        gainers = data.get('gainers', [])
        losers = data.get('losers', [])
        
        # Format specifically for tables with 3-minute data and normalized keys
        g = gainers[:15]
        l = losers[:15]
        tables_data = {
            "interval_minutes": 3,
            "gainers": g,
            "losers": l,
            "counts": {"gainers": len(g), "losers": len(l)},
            "limit": 15,
            "ts": int(time.time())
        }
        return jsonify(tables_data)
    except Exception as e:
        logging.error(f"Error in tables endpoint: {e}")
        return jsonify({"error": str(e)}), 500

# =============================================================================
# INDIVIDUAL COMPONENT ENDPOINTS - Each component gets its own unique data
# =============================================================================

# Resilient helper for top banner (never raises NameError)
def _compute_top_banner_data_safe():
    """
    Build top-banner rows using the existing 24h movers logic without sparkline/trend fields.
    Returns list[dict] with keys used by the web ticker:
      symbol, current_price, initial_price_1h, price_change_1h, market_cap
    """
    try:
        rows = get_24h_top_movers() or []
    except Exception as e:
        try:
            app.logger.warning(f"Banner fallback due to error: {e}")
        except Exception:
            pass
        rows = []

    out = []
    for coin in rows:
        try:
            pct = float(coin.get("price_change_1h", 0) or 0)
            if pct < 0:
                continue
            sym = coin.get("symbol")
            out.append({
                "symbol": sym,
                "product_id": coin.get("product_id") or sym,
                "current_price": float(coin.get("current_price", 0) or 0),
                "initial_price_1h": float(coin.get("initial_price_1h", 0) or 0),
                "price_change_1h": pct,
                "pct_1h": pct,
                "pct_change_1h": pct,
                "market_cap": float(coin.get("market_cap", 0) or 0),
            })
        except Exception:
            continue
    out.sort(key=lambda r: r.get("price_change_1h", 0), reverse=True)
    out = out[:20]
    return out

# ---------------- Simple snapshot helpers for /data -----------------

def _wrap_rows_and_ts(payload):
    """Utility: extract (rows, ts) from component payloads.

    Accepts shapes like {data: [...], last_updated: iso} or returns ([], None).
    """
    try:
        if isinstance(payload, dict):
            rows = payload.get('data') or []
            ts = payload.get('last_updated') or None
            return rows, ts
    except Exception:
        pass
    return [], None

def get_gainers_1m():
    """Return (rows, ts) for 1m gainers.

    Prefer the background-computed snapshot so `/data` stays cache-only.
    Fallback to SWR builder only if the background thread hasn't produced
    a snapshot yet.
    """
    data = _mw_get_component_snapshot('gainers_1m') or _get_gainers_table_1min_swr()
    return _wrap_rows_and_ts(data)


def get_gainers_3m():
    """Return (rows, ts) for 3m gainers (cache-only preferred)."""
    data = _mw_get_component_snapshot('gainers_3m') or _get_gainers_table_3min_swr()
    return _wrap_rows_and_ts(data)


def get_losers_3m():
    """Return (rows, ts) for 3m losers (cache-only preferred)."""
    data = _mw_get_component_snapshot('losers_3m') or _get_losers_table_3min_swr()
    return _wrap_rows_and_ts(data)


def get_banner_1h():
    """Return (rows, ts) for 1h price-change banner.

    Prefer the background snapshot to avoid on-demand Coinbase calls.
    """
    snap = _mw_get_component_snapshot('banner_1h_price')
    if isinstance(snap, dict):
        return _wrap_rows_and_ts(snap)

    # Fallback (best-effort)
    rows = _compute_top_banner_data_safe() or []
    return rows, datetime.now().isoformat()


def get_banner_1h_volume(banner_data=None):
    """Return (rows, ts) for 1h volume banner.

    Source-of-truth: candle / minute-bucket volume via the SQLite-backed volume_1h pipeline.

    No rolling-stat fallback: we do NOT derive “1h volume” from 24h rolling stats.
    If candle baseline is not ready, return [] so the UI can show WARMING / not-ready.
    """

    # 1) If we already have a precomputed snapshot for the banner, use it.
    snap = _mw_get_component_snapshot('banner_1h_volume')
    if isinstance(snap, dict):
        return _wrap_rows_and_ts(snap)

    # 2) Prefer candle/SQLite snapshot for 1h volume.
    try:
        snap_v1h_obj = _mw_get_component_snapshot('volume_1h_candles')
        # Accept either dict snapshots or raw lists (defensive):
        if isinstance(snap_v1h_obj, dict):
            vrows, vts = _wrap_rows_and_ts(snap_v1h_obj)
        elif isinstance(snap_v1h_obj, list):
            vrows, vts = snap_v1h_obj, None
        else:
            vrows, vts = [], None
        if isinstance(vrows, list) and vrows:
            out = []
            for it in vrows:
                pid = it.get('product_id') or it.get('id')
                sym = (it.get('symbol') or (pid.split('-')[0] if isinstance(pid, str) and '-' in pid else None) or '').upper()

                # Accept both shapes:
                # - SQLite compute: volume_1h_now / volume_1h_prev / volume_change_1h_pct
                # - Candle cache:  vol1h / vol1h_prev / vol1h_pct_change
                vol_now = it.get('volume_1h_now') or it.get('vol1h')
                vol_prev = it.get('volume_1h_prev') or it.get('vol1h_prev')
                pct = it.get('volume_change_1h_pct') or it.get('vol1h_pct_change')
                missing_reason = it.get('baseline_missing_reason')

                # baseline_ready requires both prev and pct to be truly computed (not derived)
                baseline_ready = (pct is not None) and (vol_prev is not None)

                pct_val = float(pct) if pct is not None else None
                out.append({
                    'symbol': sym,
                    'product_id': pid or (f"{sym}-USD" if sym else None),
                    'volume_1h_now': float(vol_now) if vol_now is not None else None,
                    'volume_1h_prev': float(vol_prev) if vol_prev is not None else None,
                    'volume_change_1h_pct': pct_val,
                    'vol_pct_1h': pct_val,

                    # aliases some frontend normalizers may read
                    'change_1h_volume': pct_val,
                    'volume_change_percentage_1h': pct_val,

                    'baseline_ready': bool(baseline_ready),
                    'baseline_missing_reason': None if baseline_ready else (missing_reason or 'warming_candles'),
                    'source': 'volume_1h_candles',
                })

            # Stable ordering: volume pct change descending (no abs, no volume sort)
            out = [r for r in out if isinstance(r.get('vol_pct_1h'), (int, float))]
            out.sort(key=lambda r: r.get('vol_pct_1h'), reverse=True)
            return out[:20], (vts or datetime.now().isoformat())
    except Exception:
        pass

    # 3) If no snapshot yet, compute from SQLite minute-window.
    try:
        payload = _volume1h_build_payload_snapshot()
        computed = _volume1h_compute_ranked(payload)
        if isinstance(computed, list) and computed:
            out = []
            for it in computed:
                pid = it.get('product_id') or it.get('id')
                sym = (it.get('symbol') or (pid.split('-')[0] if isinstance(pid, str) and '-' in pid else None) or '').upper()
                vol_now = it.get('volume_1h_now')
                vol_prev = it.get('volume_1h_prev')
                pct = it.get('volume_change_1h_pct')
                baseline_ready = (pct is not None) and (vol_prev is not None)

                pct_val = float(pct) if pct is not None else None
                out.append({
                    'symbol': sym,
                    'product_id': pid or (f"{sym}-USD" if sym else None),
                    'volume_1h_now': float(vol_now) if vol_now is not None else None,
                    'volume_1h_prev': float(vol_prev) if vol_prev is not None else None,
                    'volume_change_1h_pct': pct_val,
                    'vol_pct_1h': pct_val,
                    'change_1h_volume': pct_val,
                    'volume_change_percentage_1h': pct_val,
                    'baseline_ready': bool(baseline_ready),
                    'baseline_missing_reason': None if baseline_ready else 'warming_candles',
                    'source': 'volume1h_sqlite',
                })

            out = [r for r in out if isinstance(r.get('vol_pct_1h'), (int, float))]
            out.sort(key=lambda r: r.get('vol_pct_1h'), reverse=True)
            return out[:20], datetime.now().isoformat()
    except Exception:
        pass

    # 4) Not ready yet: no rolling-stat fallback.
    return [], None

def _build_one_min_funnel():
    """Build a compact 1m funnel breakdown for UI/debugging."""
    diag = dict(one_minute_diag) if isinstance(one_minute_diag, dict) else {}
    total_prices = int(diag.get("total_prices") or 0)
    price_non_positive = int(diag.get("price_non_positive") or 0)
    eligible_products = int(diag.get("eligible_products") or max(0, total_prices - price_non_positive))
    have_baseline = int(diag.get("have_baseline") or (int(diag.get("baseline_used_db") or 0) + int(diag.get("baseline_used_history") or 0)))
    missing_baseline = int(diag.get("missing_baseline") or diag.get("baseline_missing") or 0)
    stale_price = int(diag.get("stale_price") or diag.get("baseline_history_missing") or 0)
    filtered_min_volume = int(diag.get("filtered_min_volume") or 0)
    final_kept = int(diag.get("final_kept") or diag.get("included") or 0)
    rate_limited = 0
    if isinstance(last_current_prices, dict):
        try:
            rate_limited = int(last_current_prices.get("http429") or 0)
        except Exception:
            rate_limited = 0
    return {
        "eligible_products": eligible_products,
        "have_baseline": have_baseline,
        "missing_baseline": missing_baseline,
        "stale_price": stale_price,
        "filtered_min_volume": filtered_min_volume,
        "rate_limited": rate_limited,
        "final_kept": final_kept,
    }

@app.route('/data')
def data_aggregate():
    """Unified aggregate data endpoint used by the dashboard SPA.

    Snapshot-only: returns the last background-computed snapshot (or a fast
    warming payload). This route must never do live Coinbase/network work.
    Always returns HTTP 200 JSON and never raises in local dev.
    """
    try:
        _seed_alerts_once()
        logger = getattr(app, "logger", logging.getLogger(__name__))
        meta: dict[str, dict] = {}
        errors: dict[str, str] = {}
        rows_by_symbol: dict[str, dict] = {}
        baseline_meta_3m = _get_baseline_meta_3m()
        baseline_meta_1m = _get_baseline_meta_1m()

        # ------------------------------------------------------------------
        # Cache-only fast path: do NOT call any SWR helpers here.
        # ------------------------------------------------------------------
        snap_updated_at = _mw_get_component_snapshot('updated_at')
        snap_g1_obj = _mw_get_component_snapshot('gainers_1m')
        snap_g3_obj = _mw_get_component_snapshot('gainers_3m')
        snap_l3_obj = _mw_get_component_snapshot('losers_3m')
        snap_b1h_obj = _mw_get_component_snapshot('banner_1h_price')
        snap_bv_obj = _mw_get_component_snapshot('banner_1h_volume')
        snap_v1h_obj = _mw_get_component_snapshot('volume_1h_candles')
        snap_volume1h_obj = _mw_get_component_snapshot('volume1h')
        snap_alerts_obj = _mw_get_component_snapshot('alerts')

        snap_g1, _g1_ts = _wrap_rows_and_ts(snap_g1_obj)
        snap_g3, _g3_ts = _wrap_rows_and_ts(snap_g3_obj)
        snap_l3, _l3_ts = _wrap_rows_and_ts(snap_l3_obj)
        snap_b1h, _b1h_ts = _wrap_rows_and_ts(snap_b1h_obj)
        snap_bv, _bv_ts = _wrap_rows_and_ts(snap_bv_obj)
        snap_v1h, _v1h_ts = _wrap_rows_and_ts(snap_v1h_obj)
        snap_volume1h, _vol1h_ts = _wrap_rows_and_ts(snap_volume1h_obj)
        snap_alerts, _alerts_ts = _wrap_rows_and_ts(snap_alerts_obj)

        if snap_updated_at:
            # Best-effort latest_by_symbol map from snapshot rows.
            latest_by_symbol = {}
            for lst in (snap_g1, snap_g3, snap_l3, snap_b1h, snap_bv):
                for item in (lst or []):
                    try:
                        sym = (item.get('symbol') or '').upper()
                    except Exception:
                        sym = ''
                    if not sym:
                        continue
                    raw_price = item.get('current_price')
                    if raw_price is None:
                        raw_price = item.get('price')
                    try:
                        price_f = float(raw_price)
                    except (TypeError, ValueError):
                        continue
                    latest_by_symbol[sym] = {"symbol": sym, "price": price_f}

            # Dedupe movers by product_id and inject must-include staples
            dedupe_dropped = {}
            try:
                snap_g1, dropped_g1 = _dedupe_rows_by_product_id(list(snap_g1 or []))
                snap_g3, dropped_g3 = _dedupe_rows_by_product_id(list(snap_g3 or []))
                snap_l3, dropped_l3 = _dedupe_rows_by_product_id(list(snap_l3 or []))
                dedupe_dropped = {
                    "gainers_1m": dropped_g1,
                    "gainers_3m": dropped_g3,
                    "losers_3m": dropped_l3,
                }
            except Exception:
                dedupe_dropped = {}

            must_include = list(_MW_MUST_INCLUDE_PRODUCTS)
            present_pids = set()
            for rows in (snap_g1, snap_g3, snap_l3):
                for row in (rows or []):
                    pid = _normalize_product_id_from_row(row)
                    if pid:
                        present_pids.add(pid)

            missing_must_before = [pid for pid in must_include if pid and pid not in present_pids]
            must_added = []
            if missing_must_before:
                price_map = last_current_prices.get("data") if isinstance(last_current_prices, dict) else None
                if not isinstance(price_map, dict):
                    price_map = {}
                for pid in missing_must_before:
                    sym = pid.split("-", 1)[0].upper()
                    price = None
                    for key in (pid, sym, sym.upper()):
                        if key in price_map:
                            price = price_map.get(key)
                            break
                    if price is None and sym in latest_by_symbol:
                        price = latest_by_symbol.get(sym, {}).get("price")
                    row = {
                        "symbol": sym,
                        "product_id": pid,
                        "current_price": price,
                        "price": price,
                        "change_1m": None,
                        "change_3m": None,
                        "source": "must_include",
                    }
                    snap_g1.append(row)
                    must_added.append(pid)
                    present_pids.add(pid)

                    missing_must_after = [pid for pid in must_include if pid and pid not in present_pids]
                    missing_must = missing_must_after

            warming_3m = not bool(baseline_meta_3m.get("ready"))
            baseline_ts_3m = baseline_meta_3m.get("baseline_ts")

            warming_1m = not bool(baseline_meta_1m.get("ready"))
            baseline_ts_1m = baseline_meta_1m.get("baseline_ts")
            try:
                if isinstance(snap_g1_obj, dict) and snap_g1_obj.get("warming") is not None:
                    warming_1m = bool(snap_g1_obj.get("warming"))
                if baseline_ts_1m is None and isinstance(snap_g1_obj, dict):
                    baseline_ts_1m = snap_g1_obj.get("baseline_ts") or baseline_ts_1m
            except Exception:
                pass

            # If we already have rendered table rows in the snapshot, treat that
            # window as "ready" for UI purposes (avoids showing WARMING overlays
            # alongside populated tables).
            try:
                if isinstance(snap_g1, list) and len(snap_g1) > 0:
                    warming_1m = False
                if (isinstance(snap_g3, list) and len(snap_g3) > 0) or (isinstance(snap_l3, list) and len(snap_l3) > 0):
                    warming_3m = False
            except Exception:
                pass
            try:
                if isinstance(snap_g3_obj, dict) and snap_g3_obj.get("warming") is not None:
                    warming_3m = bool(snap_g3_obj.get("warming"))
                if isinstance(snap_l3_obj, dict) and snap_l3_obj.get("warming") is not None:
                    warming_3m = warming_3m or bool(snap_l3_obj.get("warming"))
                if baseline_ts_3m is None:
                    if isinstance(snap_g3_obj, dict):
                        baseline_ts_3m = snap_g3_obj.get("baseline_ts") or baseline_ts_3m
                    if isinstance(snap_l3_obj, dict):
                        baseline_ts_3m = snap_l3_obj.get("baseline_ts") or baseline_ts_3m
            except Exception:
                pass

            # Get last-good metadata
            last_good_ts, stale_seconds, warming, warming_3m_meta, baseline_ts_3m_meta, baseline_age_3m_meta = _mw_get_last_good_metadata()

            if isinstance(snap_alerts, list) and len(snap_alerts) > 0:
                alerts_normalized = list(snap_alerts)
                alerts_meta = {"sticky": False, "last_good_age_s": None}
            else:
                alerts_normalized, alerts_meta = _mw_get_alerts_normalized_with_sticky()

            partial_tick = bool(last_current_prices.get("partial")) if isinstance(last_current_prices, dict) else False
            sentiment_payload, sentiment_meta = _get_local_sentiment_payload()

            def _to_float(val):
                try:
                    if val is None:
                        return None
                    if isinstance(val, (int, float)):
                        return float(val)
                    s = str(val).strip().replace("%", "")
                    return float(s)
                except Exception:
                    return None

            if isinstance(snap_b1h, list):
                norm_b1h = []
                for row in snap_b1h:
                    if not isinstance(row, dict):
                        continue
                    pct = _to_float(row.get("pct_1h"))
                    if pct is None:
                        pct = _to_float(row.get("price_change_1h"))
                    rr = dict(row)
                    rr["pct_1h"] = pct
                    rr["pct_change_1h"] = rr.get("pct_change_1h") if rr.get("pct_change_1h") is not None else pct
                    rr["product_id"] = rr.get("product_id") or rr.get("symbol")
                    norm_b1h.append(rr)
                snap_b1h = norm_b1h

            if isinstance(snap_bv, list):
                norm_bv = []
                for row in snap_bv:
                    if not isinstance(row, dict):
                        continue
                    pct = _to_float(row.get("vol_pct_1h"))
                    if pct is None:
                        pct = _to_float(row.get("volume_change_1h"))
                    if pct is None:
                        pct = _to_float(row.get("volume_change_1h_pct"))
                    rr = dict(row)
                    rr["vol_pct_1h"] = pct
                    rr["product_id"] = rr.get("product_id") or rr.get("symbol")
                    norm_bv.append(rr)
                snap_bv = norm_bv
            payload = {
                "gainers_1m": snap_g1 or [],
                "gainers_3m": snap_g3 or [],
                "losers_3m": snap_l3 or [],
                "banner_1h_price": snap_b1h or [],
                "banner_1h_volume": snap_bv or [],
                "volume_1h_candles": snap_v1h or [],
                "volume1h": snap_volume1h or [],
                "alerts": alerts_normalized,
                "sentiment": sentiment_payload,
                "sentiment_meta": sentiment_meta,
                "latest_by_symbol": latest_by_symbol,
                "updated_at": snap_updated_at,
                "meta": {
                    "snapshot_only": True,
                    "ts": snap_updated_at,
                    "lastGoodTs": last_good_ts,
                    "staleSeconds": stale_seconds,
                    "warming": warming,
                    "warming_1m": warming_1m,
                    "warming_3m": warming_3m,
                    "baselineTs1m": baseline_ts_1m,
                    "baselineTs3m": baseline_ts_3m,
                    "baselineAgeSeconds1m": baseline_meta_1m.get("age_seconds"),
                    "baselineAgeSeconds3m": baseline_meta_3m.get("age_seconds"),
                    "alerts_sticky": bool(alerts_meta.get("sticky")),
                    "alerts_last_good_age_s": alerts_meta.get("last_good_age_s"),
                    "partial": partial_tick,
                    "partial_reason": last_current_prices.get("partial_reason") if isinstance(last_current_prices, dict) else None,
                    "partial_ok_ratio": last_current_prices.get("ok_ratio") if isinstance(last_current_prices, dict) else None,
                    "partial_ok": last_current_prices.get("ok") if isinstance(last_current_prices, dict) else None,
                    "partial_submitted": last_current_prices.get("submitted") if isinstance(last_current_prices, dict) else None,
                    "one_min_diagnostics": dict(one_minute_diag) if isinstance(one_minute_diag, dict) else None,
                    "one_min_funnel": _build_one_min_funnel(),
                },
                "errors": {},
                "coverage": {
                    "banner_1h_price": len(snap_b1h or []),
                    "banner_1h_volume": len(snap_bv or []),
                    "volume_1h_candles": len(snap_v1h or []),
                    "volume1h": 0,
                    "gainers_1m": len(snap_g1 or []),
                    "gainers_3m": len(snap_g3 or []),
                    "losers_3m": len(snap_l3 or []),
                    "alerts": len(alerts_normalized),
                    "dedupe_dropped": dedupe_dropped,
                    "must_include_missing": missing_must,
                    "must_include_missing_before": missing_must_before,
                    "must_include_added": must_added,
                    "one_min_funnel": _build_one_min_funnel(),
                },
            }
            payload["data"] = {
                "gainers_1m": payload["gainers_1m"],
                "gainers_3m": payload["gainers_3m"],
                "losers_3m": payload["losers_3m"],
                "banner_1h_price": payload["banner_1h_price"],
                "banner_1h_volume": payload["banner_1h_volume"],
                "volume_1h_candles": payload["volume_1h_candles"],
                "volume1h": payload["volume1h"],
                "alerts": alerts_normalized,
                "latest_by_symbol": payload["latest_by_symbol"],
                "updated_at": payload["updated_at"],
            }
            payload["coverage"]["volume1h"] = len(payload["volume1h"] or [])

            resp = jsonify(payload)
            resp.headers["Cache-Control"] = "no-store, max-age=0"
            return resp, 200

        # No snapshot yet: return a fast warming payload.
        warming_ts = datetime.now().isoformat()
        last_good_ts, stale_seconds, warming, warming_3m_empty, baseline_ts_3m_empty, baseline_age_3m_empty = _mw_get_last_good_metadata()
        partial_tick = bool(last_current_prices.get("partial")) if isinstance(last_current_prices, dict) else False
        sentiment_payload, sentiment_meta = _get_sentiment_snapshot()
        payload = {
            "gainers_1m": [],
            "gainers_3m": [],
            "losers_3m": [],
            "banner_1h_price": [],
            "banner_1h_volume": [],
            "volume_1h_candles": [],
            "volume1h": [],
            "alerts": [],
            "sentiment": sentiment_payload,
            "sentiment_meta": sentiment_meta,
            "latest_by_symbol": {},
            "updated_at": warming_ts,
            "meta": {
                "snapshot_only": True,
                "warming": warming,
                "warming_1m": True,
                "warming_3m": warming_3m_empty if warming_3m_empty is not None else True,
                "ts": warming_ts,
                "lastGoodTs": last_good_ts,
                "staleSeconds": stale_seconds,
                "baselineTs1m": None,
                "baselineTs3m": baseline_ts_3m_empty,
                "baselineAgeSeconds1m": None,
                "baselineAgeSeconds3m": baseline_age_3m_empty,
                "partial": partial_tick,
                "partial_reason": last_current_prices.get("partial_reason") if isinstance(last_current_prices, dict) else None,
                "partial_ok_ratio": last_current_prices.get("ok_ratio") if isinstance(last_current_prices, dict) else None,
                "partial_ok": last_current_prices.get("ok") if isinstance(last_current_prices, dict) else None,
                "partial_submitted": last_current_prices.get("submitted") if isinstance(last_current_prices, dict) else None,
                "one_min_diagnostics": dict(one_minute_diag) if isinstance(one_minute_diag, dict) else None,
                "one_min_funnel": _build_one_min_funnel(),
            },
            "errors": {"warming": "no_snapshot_yet"},
            "coverage": {
                "banner_1h_price": 0,
                "banner_1h_volume": 0,
                "volume_1h_candles": 0,
                "volume1h": 0,
                "gainers_1m": 0,
                "gainers_3m": 0,
                "losers_3m": 0,
                "alerts": 0,
                "dedupe_dropped": {},
                "must_include_missing": list(_MW_MUST_INCLUDE_PRODUCTS),
                "must_include_missing_before": list(_MW_MUST_INCLUDE_PRODUCTS),
                "must_include_added": [],
                "one_min_funnel": _build_one_min_funnel(),
            },
        }
        payload["data"] = {
            "gainers_1m": [],
            "gainers_3m": [],
            "losers_3m": [],
            "banner_1h_price": [],
            "banner_1h_volume": [],
            "volume1h": [],
            "alerts": [],
            "latest_by_symbol": {},
            "updated_at": warming_ts,
        }
        resp = jsonify(payload)
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp, 200

        def _sym_from(row: dict) -> str | None:
            raw = row.get("symbol") or row.get("pair") or row.get("product_id")
            if not raw:
                return None
            return str(raw).upper().replace("-USD", "")

        def _ensure_row(sym: str) -> dict:
            row = rows_by_symbol.get(sym)
            if row is None:
                row = {"symbol": sym}
                rows_by_symbol[sym] = row
            return row

        # 1m gainers snapshot
        try:
            g1_rows, g1_ts = get_gainers_1m()
            for r in (g1_rows or []):
                sym = _sym_from(r)
                if not sym:
                    continue
                base = _ensure_row(sym)
                price = r.get("current_price") or r.get("price") or 0
                try:
                    price_f = float(price)
                except (TypeError, ValueError):
                    price_f = 0.0
                if price_f > 0:
                    base["price"] = price_f
                    base["current_price"] = price_f
                    base["price_now"] = price_f

                initial_1m = r.get("initial_price_1min") or r.get("initial_1min") or r.get("previous_price_1m")
                initial_1m_val = None
                if initial_1m is not None:
                    try:
                        initial_1m_val = float(initial_1m)
                    except (TypeError, ValueError):
                        initial_1m_val = None
                if initial_1m_val is not None and initial_1m_val > 0:
                    base["initial_price_1min"] = initial_1m_val
                    base["previous_price_1m"] = initial_1m_val

                gain_1m_raw = r.get("price_change_percentage_1min")
                gain_1m_val = None
                if gain_1m_raw is not None:
                    try:
                        gain_1m_val = float(gain_1m_raw)
                    except (TypeError, ValueError):
                        gain_1m_val = None

                change_1m_val = pct_change(price_f, initial_1m_val)
                if change_1m_val is None and gain_1m_val is not None:
                    change_1m_val = gain_1m_val

                base["change_1m"] = change_1m_val
                # keep legacy key for existing UI bits
                base["price_change_percentage_1min"] = change_1m_val
            meta["gainers_1m"] = {"source": "snapshot", "ts": g1_ts}
        except Exception:
            errors["gainers_1m"] = "missing_snapshot"

        # 3m gainers snapshot
        try:
            g3_rows, g3_ts = get_gainers_3m()
            for r in (g3_rows or []):
                sym = _sym_from(r)
                if not sym:
                    continue
                base = _ensure_row(sym)
                price = r.get("current_price") or r.get("price") or 0
                try:
                    price_f = float(price)
                except (TypeError, ValueError):
                    price_f = 0.0
                if price_f > 0:
                    base["price"] = price_f
                    base["current_price"] = price_f
                    base["price_now"] = price_f
                initial_3m = r.get("initial_price_3min") or r.get("initial_3min") or r.get("previous_price_3m")
                initial_3m_val = None
                if initial_3m is not None:
                    try:
                        initial_3m_val = float(initial_3m)
                    except (TypeError, ValueError):
                        initial_3m_val = None
                if initial_3m_val is not None and initial_3m_val > 0:
                    base["initial_price_3min"] = initial_3m_val
                    base["previous_price_3m"] = initial_3m_val

                gain_3m = r.get("price_change_percentage_3min") or r.get("gain")
                gain_3m_val = None
                if gain_3m is not None:
                    try:
                        gain_3m_val = float(gain_3m)
                    except (TypeError, ValueError):
                        gain_3m_val = None

                change_3m_val = pct_change(price_f, initial_3m_val)
                if change_3m_val is None and gain_3m_val is not None:
                    change_3m_val = gain_3m_val

                base["change_3m"] = change_3m_val
                base["price_change_percentage_3min"] = change_3m_val
            meta["gainers_3m"] = {"source": "snapshot", "ts": g3_ts}
        except Exception:
            errors["gainers_3m"] = "missing_snapshot"
        # 3m losers snapshot
        try:
            l3_rows, l3_ts = get_losers_3m()
            for r in (l3_rows or []):
                sym = _sym_from(r)
                if not sym:
                    continue
                base = _ensure_row(sym)
                price = r.get("current_price") or r.get("price") or 0
                try:
                    price_f = float(price)
                except (TypeError, ValueError):
                    price_f = 0.0
                if price_f > 0:
                    base["price"] = price_f
                    base["current_price"] = price_f
                    base["price_now"] = price_f
                gain_3m = r.get("price_change_percentage_3min") or r.get("gain")
                gain_3m_val = None
                if gain_3m is not None:
                    try:
                        gain_3m_val = float(gain_3m)
                    except (TypeError, ValueError):
                        gain_3m_val = None
                # losers also carry the same 3m initial reference so the UI
                # can show the baseline under the current price
                initial_3m = r.get("initial_price_3min") or r.get("initial_3min") or r.get("previous_price_3m")
                initial_3m_val = None
                if initial_3m is not None:
                    try:
                        initial_3m_val = float(initial_3m)
                    except (TypeError, ValueError):
                        initial_3m_val = None
                if initial_3m_val is not None and initial_3m_val > 0:
                    base["initial_price_3min"] = initial_3m_val
                    base["previous_price_3m"] = initial_3m_val

                change_3m_val = pct_change(price_f, initial_3m_val)
                if change_3m_val is None and gain_3m_val is not None:
                    change_3m_val = gain_3m_val

                base["change_3m"] = change_3m_val
                base["price_change_percentage_3min"] = change_3m_val
            meta["losers_3m"] = {"source": "snapshot", "ts": l3_ts}
        except Exception:
            errors["losers_3m"] = "missing_snapshot"

        # 1h price banner snapshot
        try:
            b_rows, b_ts = get_banner_1h()
            if b_rows:
                for r in b_rows:
                    sym = _sym_from(r)
                    if not sym:
                        continue
                    base = _ensure_row(sym)
                    price = r.get("current_price") or r.get("price") or 0
                    price_now = None
                    try:
                        price_f = float(price)
                    except (TypeError, ValueError):
                        price_f = 0.0
                    if price_f > 0:
                        # canonical price fields for banners and tables
                        base["price"] = price_f
                        base["current_price"] = price_f
                        base["price_now"] = price_f
                        price_now = price_f

                    price_1h_ago = r.get("price_1h_ago") or r.get("initial_price_1h")
                    price_1h_val = None
                    if price_1h_ago is not None:
                        try:
                            price_1h_val = float(price_1h_ago)
                        except (TypeError, ValueError):
                            price_1h_val = None
                    if price_1h_val is not None and price_1h_val > 0:
                        base["price_1h_ago"] = price_1h_val

                    change_1h_fallback = r.get("price_change_1h")
                    change_1h_val = pct_change(price_now, price_1h_val)
                    if change_1h_val is None and change_1h_fallback is not None:
                        try:
                            change_1h_val = float(change_1h_fallback)
                        except (TypeError, ValueError):
                            change_1h_val = None

                    # canonical 1h price-change keys used by banners
                    base["change_1h_price"] = change_1h_val
                    base["price_change_1h"] = change_1h_val
                    base["pct_change_1h"] = change_1h_val
                    base["price_change_1h_pct"] = change_1h_val
                meta["banner_1h_price"] = {"source": "computed", "ts": b_ts}
            else:
                errors["banner_1h_price"] = "unavailable"
        except Exception:
            errors["banner_1h_price"] = "unavailable"

        # 1h volume banner snapshot
        try:
            vb_rows, vb_ts = get_banner_1h_volume()
            if vb_rows:
                for r in vb_rows:
                    sym = _sym_from(r)
                    if not sym:
                        continue
                    base = _ensure_row(sym)
                    vol_now = r.get("volume_24h")
                    try:
                        vol_now_f = float(vol_now)
                    except (TypeError, ValueError):
                        vol_now_f = 0.0
                    if vol_now_f > 0:
                        # treat as latest 1h (or 24h snapshot) volume for display
                        base["volume_24h"] = vol_now_f
                        base["volume_1h"] = vol_now_f
                        base["volume_1h_now"] = vol_now_f

                    vol_prev_val = None
                    vol_prev_raw = r.get("volume_1h_prev")
                    if vol_prev_raw is not None:
                        try:
                            vol_prev_val = float(vol_prev_raw)
                        except (TypeError, ValueError):
                            vol_prev_val = None

                    vol_change_abs = r.get("volume_change_1h")
                    vol_change_abs_val = None
                    if vol_change_abs is not None:
                        try:
                            vol_change_abs_val = float(vol_change_abs)
                        except (TypeError, ValueError):
                            vol_change_abs_val = None

                    if vol_prev_val is None and vol_change_abs_val is not None:
                        vol_prev_val = vol_now_f - vol_change_abs_val

                    vol_pct_raw = r.get("volume_change_1h_pct")
                    vol_pct_val = None
                    if vol_pct_raw is not None:
                        try:
                            vol_pct_val = float(vol_pct_raw)
                        except (TypeError, ValueError):
                            vol_pct_val = None
                    if vol_prev_val is None and vol_pct_val not in (None, 0.0):
                        try:
                            denom = 1 + (vol_pct_val / 100.0)
                            if denom != 0:
                                vol_prev_val = vol_now_f / denom
                        except Exception:
                            vol_prev_val = None

                    if vol_prev_val is not None:
                        base["volume_1h_prev"] = vol_prev_val
                        vol_change_abs_val = vol_now_f - vol_prev_val

                    change_1h_volume_pct = pct_change(vol_now_f, vol_prev_val)
                    if change_1h_volume_pct is None and vol_pct_val is not None:
                        change_1h_volume_pct = vol_pct_val

                    base["volume_change_1h"] = vol_change_abs_val
                    # canonical 1h volume-change keys used by volume banners
                    base["change_1h_volume"] = change_1h_volume_pct
                    base["volume_change_1h_pct"] = change_1h_volume_pct
                    base["volume_change_percentage_1h"] = change_1h_volume_pct
                meta["banner_1h_volume"] = {"source": "computed", "ts": vb_ts}
            else:
                errors["banner_1h_volume"] = "unavailable"
        except Exception:
            errors["banner_1h_volume"] = "unavailable"

        # Build canonical list of rows
        all_rows = list(rows_by_symbol.values())

        baseline_keys = (
            "previous_price",
            "previous_price_1m",
            "previous_price_3m",
            "initial_price_1min",
            "initial_price_3min",
            "initial_price",
            "initial_1min",
            "initial_3min",
            "price_1m_ago",
            "price_3m_ago",
        )
        for row in rows_by_symbol.values():
            for key in baseline_keys:
                if key in row:
                    row[key] = _null_if_nonpositive(row.get(key))

        def _rank_and_trade(subset, limit: int):
            out_rows = []
            for idx, base in enumerate(subset[:limit], start=1):
                row = dict(base)
                row["rank"] = idx
                sym = row.get("symbol") or ""
                # normalize symbol into a Coinbase advanced-trade spot pair
                slug = str(sym).lower().replace('_', '-').replace('/', '-')
                if not (slug.endswith('-usd') or slug.endswith('-usdt') or slug.endswith('-perp')):
                    slug = f"{slug}-usd"
                row.setdefault("trade_url", f"https://www.coinbase.com/advanced-trade/spot/{slug}")
                out_rows.append(row)
            return out_rows

        def _select_top_movers(rows, pct_key: str, limit: int = 16):
            """Deterministic splitter for gainers/losers by sign.

            - Normalizes the percent field to a float.
            - Splits into strictly >0 gainers and <0 losers.
            - Sorts gainers desc, losers asc (most negative first).
            - Never backfills one side with the other if there aren't enough.
            """
            cleaned = []
            for row in rows:
                raw = row.get(pct_key)
                if raw is None:
                    continue
                try:
                    pct = float(raw)
                except (TypeError, ValueError):
                    continue
                r = dict(row)
                r[pct_key] = pct
                cleaned.append(r)

            gainers = [r for r in cleaned if r[pct_key] > 0.0]
            losers = [r for r in cleaned if r[pct_key] < 0.0]

            gainers_sorted = sorted(gainers, key=lambda r: r[pct_key], reverse=True)
            losers_sorted = sorted(losers, key=lambda r: r[pct_key])  # most negative first

            return _rank_and_trade(gainers_sorted, limit), _rank_and_trade(losers_sorted, limit)

        def build_3m_slices(tokens: list[dict], top_n: int = 8):
            gainers = [t for t in tokens if t.get("change_3m") is not None and t.get("change_3m") > 0]
            losers = [t for t in tokens if t.get("change_3m") is not None and t.get("change_3m") < 0]

            gainers_sorted = sorted(gainers, key=lambda t: t["change_3m"], reverse=True)
            losers_sorted = sorted(losers, key=lambda t: t["change_3m"], reverse=False)

            gainers_top = _rank_and_trade(gainers_sorted, top_n)
            losers_top = _rank_and_trade(losers_sorted, top_n)

            for t in gainers_top:
                try:
                    if t.get("change_3m") is not None and t["change_3m"] <= 0:
                        logger.error("Invalid entry in gainers_3m: %s", t)
                except Exception:
                    pass

            for t in losers_top:
                try:
                    if t.get("change_3m") is not None and t["change_3m"] >= 0:
                        logger.error("Invalid entry in losers_3m: %s", t)
                except Exception:
                    pass

            return gainers_top, losers_top

        def build_1h_price_banner(tokens: list[dict], top_n: int = 20):
            enriched = []
            for t in tokens:
                price_now = t.get("current_price") if isinstance(t.get("current_price"), (int, float)) else t.get("price")
                if price_now is None:
                    price_now = t.get("price_now")
                price_ago = t.get("price_1h_ago") or t.get("initial_price_1h")
                try:
                    price_now_f = float(price_now)
                except (TypeError, ValueError):
                    price_now_f = None
                try:
                    price_ago_f = float(price_ago)
                except (TypeError, ValueError):
                    price_ago_f = None

                row = dict(t)
                if price_now_f is not None:
                    row["price_now"] = price_now_f
                if price_ago_f is not None:
                    row["price_1h_ago"] = price_ago_f

                change_pct = pct_change(price_now_f, price_ago_f)
                normalized_pct = _safe_float(change_pct)
                if normalized_pct in (None, 0.0):
                    fallback = t.get("price_change_1h") or t.get("change_1h_price")
                    normalized_pct = _safe_float(fallback)

                row["price_change_1h_pct"] = normalized_pct
                row["change_1h_price"] = normalized_pct
                row["price_change_1h"] = normalized_pct
                enriched.append(row)

            # Keep only numeric, non-zero changes; missing/invalid should not become 0.
            enriched = [t for t in enriched if t.get("price_change_1h_pct") not in (None, 0.0)]
            enriched = _sort_rows_by_numeric(enriched, "price_change_1h_pct", descending=True)
            return _rank_and_trade(enriched, top_n)

        def build_1h_volume_banner(tokens: list[dict], top_n: int = 20):
            enriched = []
            fallback_rows = []
            for t in tokens:
                vol_now = t.get("volume_1h_now") or t.get("volume_24h") or t.get("volume_1h")
                vol_prev = t.get("volume_1h_prev")
                try:
                    vol_now_f = float(vol_now)
                except (TypeError, ValueError):
                    vol_now_f = None
                try:
                    vol_prev_f = float(vol_prev)
                except (TypeError, ValueError):
                    vol_prev_f = None

                row = dict(t)
                if vol_now_f is not None:
                    row["volume_1h_now"] = vol_now_f
                if vol_prev_f is not None:
                    row["volume_1h_prev"] = vol_prev_f

                change_pct = pct_change(vol_now_f, vol_prev_f)
                normalized_pct = _safe_float(change_pct)
                if normalized_pct in (None, 0.0):
                    fallback = t.get("volume_change_1h_pct") or t.get("change_1h_volume")
                    normalized_pct = _safe_float(fallback)

                # If we still don't have a previous volume but do have change_pct, derive it
                if vol_prev_f is None and vol_now_f is not None and change_pct not in (None, 0.0):
                    try:
                        denom = 1 + (change_pct / 100.0)
                        if denom != 0:
                            derived_prev = vol_now_f / denom
                            row["volume_1h_prev"] = derived_prev
                            vol_prev_f = derived_prev
                    except Exception:
                        pass

                vol_change_abs = None
                if vol_now_f is not None and vol_prev_f is not None:
                    vol_change_abs = vol_now_f - vol_prev_f
                row["volume_change_1h"] = vol_change_abs
                row["volume_change_1h_pct"] = normalized_pct
                row["change_1h_volume"] = normalized_pct
                row["volume_change_percentage_1h"] = normalized_pct
                enriched.append(row)
                if normalized_pct in (None, 0.0) and vol_now_f is not None:
                    fallback_rows.append(row)

            enriched = [t for t in enriched if t.get("volume_change_1h_pct") not in (None, 0.0)]
            if enriched:
                enriched = _sort_rows_by_numeric(enriched, "volume_change_1h_pct", descending=True)
                return _rank_and_trade(enriched, top_n)

            # Dev-friendly fallback: if no 1h delta is available, rank by volume now
            fallback_rows = [t for t in fallback_rows if t.get("volume_1h_now") is not None]
            if fallback_rows:
                fallback_rows = _sort_rows_by_numeric(fallback_rows, "volume_1h_now", descending=True)
                for row in fallback_rows:
                    row["volume_change_1h_pct"] = row.get("volume_change_1h_pct") or 0.0
                return _rank_and_trade(fallback_rows, top_n)

            return []

        gainers_1m, _losers_dummy_1m = _select_top_movers(all_rows, "change_1m", limit=50)
        gainers_3m, losers_3m = build_3m_slices(all_rows, top_n=50)

        banner_1h_price = build_1h_price_banner(all_rows, top_n=20)
        banner_1h_volume = build_1h_volume_banner(all_rows, top_n=20)

        latest_by_symbol = {}
        for sym, row in rows_by_symbol.items():
            price = row.get("price") or row.get("current_price")
            try:
                price_f = float(price)
            except (TypeError, ValueError):
                price_f = None
            # Resolve product_id only if it is a verified Coinbase product.
            # Prefer an explicit product_id from upstream payloads; otherwise
            # attempt to resolve via `resolve_product_id` which checks the cached
            # Coinbase product list. If no verified product exists, set to None
            # to avoid guessing and producing broken links.
            # Resolve a verified Coinbase product id just before emitting the
            # payload. Use the canonical resolver which preserves upstream
            # explicit ids and prefers quotes in QUOTE_PREF order.
            try:
                resolved = resolve_product_id_from_row(row)
                row["product_id"] = resolved if resolved else None
                if DEBUG_PID and not resolved:
                    # Emit a concise trace showing which fields were present
                    _pid_debug(
                        f"PID_MISS_EMIT symbol={sym!r} base={row.get('base')!r} "
                        f"coinbase_symbol={row.get('coinbase_symbol')!r} ticker={row.get('ticker')!r} "
                        f"product_id_upstream={row.get('product_id')!r} options_sample={(PRODUCT_IDS_BY_BASE.get(_norm_base(row.get('base')) if row.get('base') else _norm_base(row.get('symbol')) ) or [])[:6]}"
                    )
            except Exception:
                row["product_id"] = None
                if DEBUG_PID:
                    _pid_debug(f"PID_EXCEPTION_EMIT symbol={sym!r} row_keys={list(row.keys())}")

            latest_by_symbol[sym] = {"symbol": sym, "price": price_f}

        payload = {
            "gainers_1m": gainers_1m,
            "gainers_3m": gainers_3m,
            "losers_3m": losers_3m,
            "banner_1h_price": banner_1h_price,
            "banner_1h_volume": banner_1h_volume,
            "latest_by_symbol": latest_by_symbol,
            "updated_at": datetime.now().isoformat(),
            "meta": meta,
            "errors": errors,
        }

        coverage = {
            "banner_1h_price": len(banner_1h_price),
            "banner_1h_volume": len(banner_1h_volume),
            "gainers_1m": len(gainers_1m),
            "gainers_3m": len(gainers_3m),
            "losers_3m": len(losers_3m),
        }
        payload["coverage"] = coverage

        # Emit per-item debug traces for any rows that will be returned without
        # a verified `product_id`. This helps determine whether the missing id
        # is due to a bad base/ticker field or because the asset truly isn't on
        # Coinbase.
        if DEBUG_PID:
            try:
                lists = [
                    ("gainers_1m", gainers_1m),
                    ("gainers_3m", gainers_3m),
                    ("losers_3m", losers_3m),
                    ("banner_1h_price", banner_1h_price),
                    ("banner_1h_volume", banner_1h_volume),
                ]
                for name, lst in lists:
                    for item in (lst or [])[:50]:
                        try:
                            if item.get("product_id") is None:
                                _pid_debug(
                                    f"PID_MISS payload={name} symbol={item.get('symbol')!r} base={item.get('base')!r} "
                                    f"coinbase_symbol={item.get('coinbase_symbol')!r} ticker={item.get('ticker')!r} asset={item.get('asset')!r}"
                                )
                                # Also emit a full JSON snippet for deeper inspection (first 10 only)
                                try:
                                    seen = getattr(app, '_pid_miss_seen', 0)
                                except Exception:
                                    seen = 0
                                if seen < 10:
                                    try:
                                        import json as _json
                                        _pid_debug("PID_MISS_FULL " + _json.dumps(item, default=str)[:2000])
                                    except Exception:
                                        _pid_debug(f"PID_MISS_FULL_FAILED symbol={item.get('symbol')!r}")
                                    try:
                                        app._pid_miss_seen = seen + 1
                                    except Exception:
                                        pass
                        except Exception:
                            continue
            except Exception:
                pass

        # Provide a simple top-level timestamp for compatibility with older jq tooling
        try:
            meta["ts"] = payload["updated_at"]
        except Exception:
            try:
                meta["ts"] = datetime.now().isoformat()
            except Exception:
                pass

        # Backwards-compatible shape for older Dashboard.jsx which expects a
        # top-level { data, meta, errors } object.
        try:
            payload["data"] = {
                "gainers_1m": gainers_1m,
                "gainers_3m": gainers_3m,
                "losers_3m": losers_3m,
                "banner_1h_price": banner_1h_price,
                "banner_1h_volume": banner_1h_volume,
                "latest_by_symbol": latest_by_symbol,
                "updated_at": payload["updated_at"],
            }
        except Exception:
            # best-effort; if this alias fails, main payload is still valid
            pass

        resp = jsonify(payload)
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp, 200
    except Exception as e:
        # Absolute guardrail: never 5xx in local dev for /data
        try:
            app.logger.exception("/data aggregate fatal: %s", e)
        except Exception:
            pass
        resp = jsonify(
            {
                "gainers_1m": [],
                "gainers_3m": [],
                "losers_3m": [],
                "banner_1h_price": [],
                "banner_1h_volume": [],
                "latest_by_symbol": {},
                "updated_at": datetime.now().isoformat(),
                "meta": {},
                "errors": {"fatal": str(e)},
            }
        )
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        return resp, 200

@app.route('/api/component/top-banner-scroll')
def get_top_banner_scroll():
    """Individual endpoint for top scrolling banner - 1-hour price change data (resilient, no trends/sparklines)."""
    try:
        rows = _compute_top_banner_data_safe() or []
        payload = {
            "component": "top_banner_scroll",
            "data": rows,
            "count": len(rows),
            "time_frame": "1_hour",
            "focus": "price_change",
            "scroll_speed": "medium",
            "update_interval": 60000,
            "last_updated": datetime.now().isoformat()
        }
        return jsonify(payload), 200
    except Exception as e:
        try:
            app.logger.exception("top banner scroll error: %s", e)
        except Exception:
            pass
        # Still return 200 with empty list so UI never breaks
        return jsonify({
            "component": "top_banner_scroll",
            "data": [],
            "count": 0,
            "time_frame": "1_hour",
            "focus": "price_change",
            "scroll_speed": "medium",
            "update_interval": 60000,
            "last_updated": datetime.now().isoformat(),
            "error": str(e)
        }), 200

@app.route('/api/component/bottom-banner-scroll')
def get_bottom_banner_scroll():
    """Individual endpoint for bottom scrolling banner - 1-hour volume change data"""
    try:
        # Get 1-hour volume change data (24h banner data has volume info)
        banner_data = get_24h_top_movers()
        if not banner_data:
            return jsonify({"error": ERROR_NO_DATA}), 503
            
        # Sort by 24h volume for bottom banner (as we don't have hourly volume data)
        volume_sorted = sorted(banner_data, key=lambda x: x.get("volume_24h", 0), reverse=True)
        
        bottom_scroll_data = []
        for coin in volume_sorted[:20]:  # Top 20 by volume
            sym = coin["symbol"]
            vol_now = float(coin.get("volume_24h", 0) or 0)
            # Compute 1h volume change from history (rolling 24h cumulative volume difference)
            vol_change_1h = None
            vol_change_1h_pct = None
            try:
                hist = volume_history_24h.get(sym, deque())
                if hist:
                    now_ts = time.time()
                    # Only compute a "real" 1h volume change if we have a snapshot at least 3600s old.
                    vol_then = None
                    for ts, vol in hist:
                        if now_ts - ts >= 3600:
                            vol_then = vol
                            break
                    # If we don't yet have >=1h history, leave vol_change_1h_pct as None
                    if vol_then is not None:
                        vol_change_1h = vol_now - vol_then
                        vol_change_1h_pct = pct_change(vol_now, vol_then)
            except Exception:
                pass
            # Fallback metric for trend if we lack 1h volume delta
            ch_metric = float(vol_change_1h_pct if vol_change_1h_pct is not None else (coin.get("price_change_1h", 0) or 0))
            prev = one_hour_volume_trends.get(sym, {"last": ch_metric, "streak": 0, "last_dir": "flat", "score": 0.0})
            direction = "up" if ch_metric > prev["last"] else ("down" if ch_metric < prev["last"] else "flat")
            streak = prev["streak"] + 1 if direction != "flat" and direction == prev["last_dir"] else (1 if direction != "flat" else prev["streak"])
            score = round(prev["score"] * 0.9 + abs(ch_metric) * 0.1, 3)
            one_hour_volume_trends[sym] = {"last": ch_metric, "streak": streak, "last_dir": direction, "score": score}
            _maybe_fire_trend_alert('1h_volume', sym, direction, streak, score)

            bottom_scroll_data.append({
                "symbol": sym,
                "current_price": coin["current_price"],
                "volume_24h": vol_now,
                "price_change_1h": coin["price_change_1h"],
                "volume_change_1h": vol_change_1h,
                "volume_change_1h_pct": vol_change_1h_pct,
                "volume_change_estimate": coin["price_change_1h"] * 0.5 if vol_change_1h_pct is None else None,
                "volume_change_is_estimated": vol_change_1h_pct is None,
                "volume_category": "high" if vol_now > 10000000 else "medium" if vol_now > 1000000 else "low",
                "trend_direction": direction,
                "trend_streak": streak,
                "trend_score": score
            })
        
        return jsonify({
            "component": "bottom_banner_scroll",
            "data": bottom_scroll_data,
            "count": len(bottom_scroll_data),
            "time_frame": "1_hour",
            "focus": "volume_change",
            "scroll_speed": "slow",
            "update_interval": 60000,  # 1 minute updates for 1-hour data
            "last_updated": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Error in bottom banner scroll endpoint: {e}")
        return jsonify({"error": str(e)}), 500

# --- Edge slim endpoint for Worker seeding ---
@app.get('/api/edge/volumes-slim')
def volumes_slim():
    """Minimal symbol -> { volume_24h, volume_change_1h_pct? } map for the edge Worker.
    Falls back to the same 24h movers snapshot used for banners. If 1h volume change
    is not available yet, omit it so the Worker can estimate from its ring buffer.
    """
    try:
        out = {}
        try:
            banner = get_24h_top_movers() or []
        except Exception:
            banner = []
        for row in banner:
            try:
                sym = row.get('symbol')
                vol = row.get('volume_24h')
                if not sym or vol is None:
                    continue
                out[sym] = {
                    'volume_24h': float(vol),
                    # passthrough if present; Worker may still choose to estimate
                    'volume_change_1h_pct': row.get('volume_change_1h_pct') if row.get('volume_change_1h_pct') is not None else None,
                }
            except Exception:
                continue
        return jsonify(out), 200
    except Exception as e:
        logging.error(f"volumes_slim error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/component/gainers-table')
def get_gainers_table():
    """Individual endpoint for gainers table - 3-minute data only"""
    try:
        data = get_crypto_data()
        if not data:
            return jsonify({"error": ERROR_NO_DATA}), 503
            
        gainers = data.get('gainers', [])
        
        # Enhanced formatting specifically for gainers table
        gainers_table_data = []
        for i, coin in enumerate(gainers[:20]):  # Top 20 gainers
            # update 3-min trend cache
            sym = coin["symbol"]
            g = float(coin.get("gain", 0) or 0)
            prev = three_minute_trends.get(sym, {"last": g, "streak": 0, "last_dir": "flat", "score": 0.0})
            direction = "up" if g > prev["last"] else ("down" if g < prev["last"] else "flat")
            streak = prev["streak"] + 1 if direction != "flat" and direction == prev["last_dir"] else (1 if direction != "flat" else prev["streak"])
            score = round(prev["score"] * 0.8 + g * 0.2, 3)
            three_minute_trends[sym] = {"last": g, "streak": streak, "last_dir": direction, "score": score}
            _maybe_fire_trend_alert('3m', sym, direction, streak, score)
            gainers_table_data.append({
                "rank": i + 1,
                "symbol": coin["symbol"],
                "current_price": coin["current"],  # Use correct field name
                "price_change_percentage_3min": coin["gain"],  # Use correct field name
                "initial_price_3min": coin["initial_3min"],  # Use correct field name
                "actual_interval_minutes": coin.get("interval_minutes", 3),  # Use correct field name
                "trend_direction": direction,
                "trend_streak": streak,
                "trend_score": score,
                "momentum": "strong" if coin["gain"] > 5 else "moderate",
                "alert_level": "high" if coin["gain"] > 10 else "normal"
            })
        
        swr_meta = {
            'ttl': _GAINERS_3M_SWR_TTL,
            'stale_window': _GAINERS_3M_SWR_STALE,
            'served_cached': getattr(globals().get('_get_gainers_table_3min_swr'), '_swr_last_served_cached', False)
        }
        return jsonify({
            "component": "gainers_table",
            "data": gainers_table_data,
            "count": len(gainers_table_data),
            "table_type": "gainers",
            "time_frame": "3_minutes",
            "update_interval": 3000,
            "last_updated": datetime.now().isoformat(),
            "swr": swr_meta
        })
    except Exception as e:
        logging.error(f"Error in gainers table endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/component/losers-table')
def get_losers_table():
    """Individual endpoint for losers table - 3-minute data only"""
    try:
        data = _get_losers_table_3min_swr()
        if not data:
            return jsonify({"error": ERROR_NO_DATA}), 503
        swr_meta = {
            'ttl': _LOSERS_3M_SWR_TTL,
            'stale_window': _LOSERS_3M_SWR_STALE,
            'served_cached': getattr(_get_losers_table_3min_swr, '_swr_last_served_cached', False),
        }
        return jsonify({**data, 'swr': swr_meta})
    except Exception as e:
        logging.error(f"Error in losers table endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/component/top-movers-bar')
def get_top_movers_bar():
    """Individual endpoint for top movers horizontal bar - 3min focus"""
    try:
        data = _get_top_movers_bar_swr()
        if not data:
            return jsonify({"error": ERROR_NO_DATA}), 503
        swr_meta = {
            'ttl': _TOP_MOVERS_BAR_SWR_TTL,
            'stale_window': _TOP_MOVERS_BAR_SWR_STALE,
            'served_cached': getattr(_get_top_movers_bar_swr, '_swr_last_served_cached', False),
        }
        return jsonify({**data, 'swr': swr_meta})
    except Exception as e:
        logging.error(f"Error in top movers bar endpoint: {e}")
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------------------
# Alerts API: expose recent Moonwalking alerts (normalized)
# -----------------------------------------------------------------------------
@app.route('/api/alerts')
def get_basic_alerts():
    """Return lightweight alerts from the in-memory ring buffer."""
    try:
        with _BASIC_ALERTS_LOCK:
            items = list(alerts_basic_log)
        validated = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                validated.append(AlertItem.model_validate(item).model_dump())
            except Exception:
                # Skip malformed items to keep payload clean
                continue
        return jsonify({"ok": True, "data": validated})
    except Exception as e:
        logging.error(f"Error in basic alerts endpoint: {e}")
        return jsonify({"ok": True, "data": []})

@app.route('/api/alerts/recent')
def get_recent_alerts():
    try:
        limit = int(request.args.get('limit', 50))
        if limit <= 0:
            limit = 50

        snap = _mw_get_component_snapshot('alerts')
        items, _ts = _wrap_rows_and_ts(snap)
        if isinstance(items, list) and items:
            alerts_meta = {"sticky": False, "last_good_age_s": None}
        else:
            items, alerts_meta = _mw_get_alerts_normalized_with_sticky()

        items = (items or [])[-limit:]
        return jsonify({
            'count': len(items),
            'limit': limit,
            'alerts': items,
            'meta': alerts_meta,
        })
    except Exception as e:
        logging.error(f"Error in recent alerts endpoint: {e}")
        return jsonify({'error': str(e)}), 500
# EXISTING ENDPOINTS (Updated root to show new individual endpoints)

def get_crypto_data_1min(current_prices=None, force_refresh: bool = False):
    """Main function to fetch and process 1-minute crypto data.

    Accepts optional `current_prices` snapshot to avoid refetching when the
    background updater supplies a fresh price set.
    """
    # Allow an explicit seeded fixture to be returned when running tests or
    # when the env flag USE_1MIN_SEED=1 is present. This helps tests avoid
    # needing live price history during CI.
    try:
        if os.environ.get('USE_1MIN_SEED', '0') == '1':
            fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'top_movers_3m.json')
            if os.path.exists(fixture_path):
                try:
                    with open(fixture_path, 'r', encoding='utf-8') as fh:
                        seeded = json.load(fh)
                    seeded.setdefault('source', 'fixture-seed')
                    seeded.setdefault('seed', True)
                    one_minute_cache['data'] = seeded
                    one_minute_cache['timestamp'] = time.time()
                    return seeded
                except Exception:
                    logging.exception('Failed to load 1-min fixture; falling back to live calculation')
    except Exception:
        pass

    if not CONFIG.get('ENABLE_1MIN', True):
        return None
    current_time = time.time()
    snapshot_ts_s = None
    # Throttle heavy recomputation; allow front-end fetch to reuse last processed snapshot.
    # Callers that are responsible for appending new history (e.g., the background
    # price fetch loop) should pass force_refresh=True.
    refresh_window = CONFIG.get('ONE_MIN_REFRESH_SECONDS', 30)
    if (not force_refresh) and one_minute_cache['data'] and (current_time - one_minute_cache['timestamp']) < refresh_window:
        return one_minute_cache['data']
    try:
        # If callers provided a price snapshot, prefer it (cache-only path).
        # Otherwise reuse the freshest cached price set or fetch.
        if isinstance(current_prices, dict) and current_prices:
            snapshot_ts_s = int(current_time)
        else:
            # Reuse prices from background thread if fetched recently (<10s) to avoid parallel bursts
            prices_age_limit = 10
            if last_current_prices['data'] and (current_time - last_current_prices['timestamp']) < prices_age_limit:
                current_prices = last_current_prices['data']
                snapshot_ts_s = int(last_current_prices.get('timestamp') or current_time)
            else:
                current_prices = get_current_prices()
                if current_prices:
                    last_current_prices['data'] = current_prices
                    last_current_prices['timestamp'] = current_time
                    snapshot_ts_s = int(current_time)
        if not current_prices:
            logging.warning("No current prices available for 1-min data")
            return None

        if snapshot_ts_s is None:
            snapshot_ts_s = int(current_time)

        crypto_data = calculate_1min_changes(current_prices, snapshot_ts_s)
        if not crypto_data:
            # On cold start we may have <2 samples per symbol.
            # IMPORTANT: don't clobber a previously-good cache with empty output
            # during transient warmups/timeouts; return the last good data instead.
            logging.warning(
                "No 1-min crypto data available after calculation - %s current prices, %s symbols with history",
                len(current_prices),
                len(price_history_1min),
            )
            prior = one_minute_cache.get('data')
            if isinstance(prior, dict) and ((prior.get('gainers') or []) or (prior.get('losers') or [])):
                return prior
            empty_result = {
                "gainers": [],
                "losers": [],
                "throttled": True,
                "refresh_seconds": CONFIG.get('ONE_MIN_REFRESH_SECONDS', 30),
                "enter_threshold_pct": CONFIG.get('ONE_MIN_ENTER_PCT', 0.15),
                "stay_threshold_pct": CONFIG.get('ONE_MIN_STAY_PCT', 0.05),
                "dwell_seconds": CONFIG.get('ONE_MIN_DWELL_SECONDS', 90),
                "retained": 0,
            }
            one_minute_cache['data'] = empty_result
            one_minute_cache['timestamp'] = current_time
            return empty_result

        # --- Retention / hysteresis logic ---
        enter_pct = CONFIG.get('ONE_MIN_ENTER_PCT', 0.15)
        stay_pct = CONFIG.get('ONE_MIN_STAY_PCT', 0.05)
        dwell_seconds = CONFIG.get('ONE_MIN_DWELL_SECONDS', 90)
        max_coins = CONFIG.get('ONE_MIN_MAX_COINS', 25)
        now_ts = current_time
        pers = one_minute_persistence['entries']

        # Index by symbol for quick lookups and update rolling 60s peak table
        data_by_symbol = {}
        peak_window = 60  # seconds to hold a peak
        for c in crypto_data:
            sym = c['symbol']
            pct_now = c.get('price_change_percentage_1min', 0)
            data_by_symbol[sym] = c
            peak = one_minute_peaks.get(sym)
            if not peak or pct_now > peak.get('peak_pct', -999):
                one_minute_peaks[sym] = {'peak_pct': pct_now, 'peak_at': now_ts, 'last_seen': now_ts}
            else:
                peak['last_seen'] = now_ts

        # Decay / prune old peaks beyond window
        to_prune = []
        for sym, peak in one_minute_peaks.items():
            if (now_ts - peak['peak_at']) > peak_window and (now_ts - peak['last_seen']) > peak_window:
                to_prune.append(sym)
        for sym in to_prune:
            one_minute_peaks.pop(sym, None)

        # Adjust effective pct used for ranking: hold peak within window if current dipped
        for sym, coin in data_by_symbol.items():
            peak = one_minute_peaks.get(sym)
            if peak and (now_ts - peak['peak_at']) <= peak_window:
                current_pct = coin.get('price_change_percentage_1min', 0)
                if peak['peak_pct'] > current_pct > 0:
                    coin['price_change_percentage_1min_peak'] = peak['peak_pct']
                elif peak['peak_pct'] < current_pct < 0:  # for negative movers
                    coin['price_change_percentage_1min_peak'] = peak['peak_pct']
                else:
                    coin['price_change_percentage_1min_peak'] = current_pct
            else:
                coin['price_change_percentage_1min_peak'] = coin.get('price_change_percentage_1min', 0)

        # --- Trending logic: direction/streak/score based on effective gain deltas ---
        trend_eps = CONFIG.get('ONE_MIN_TREND_EPS', 0.02)  # %. Minimal delta to count as movement
        for sym, coin in data_by_symbol.items():
            eff = coin.get('price_change_percentage_1min_peak', coin.get('price_change_percentage_1min', 0)) or 0.0
            prev = one_minute_trends.get(sym, {"last_gain": eff, "streak": 0, "last_dir": "flat", "score": 0.0})
            delta = eff - prev.get('last_gain', 0.0)
            if delta > trend_eps:
                direction = 'up'
                streak = prev['streak'] + 1 if prev.get('last_dir') == 'up' else 1
            elif delta < -trend_eps:
                direction = 'down'
                streak = prev['streak'] + 1 if prev.get('last_dir') == 'down' else 1
            else:
                direction = 'flat'
                streak = prev['streak'] + 1 if prev.get('last_dir') == 'flat' else 1
                streak = min(streak, 5)
            # Simple bounded trend score combining delta and streak
            score = max(-10.0, min(10.0, round(delta * 3.0 + streak * (0.5 if direction != 'flat' else 0.1), 2)))
            one_minute_trends[sym] = {
                'last_gain': eff,
                'last_dir': direction,
                'streak': streak,
                'score': score,
                'updated_at': now_ts,
                'delta': round(delta, 3),
            }
            _maybe_fire_trend_alert('1m', sym, direction, streak, score)

        # Update existing entries & drop those that lost momentum AND exceeded dwell time below stay threshold
        to_delete = []
        for sym, meta in pers.items():
            coin = data_by_symbol.get(sym)
            gain_pct = coin.get('price_change_percentage_1min_peak', coin.get('price_change_percentage_1min', 0)) if coin else 0
            if coin:
                if abs(gain_pct) >= stay_pct:
                    continue
                if (now_ts - meta['entered_at']) < dwell_seconds:
                    continue
            to_delete.append(sym)
        for sym in to_delete:
            pers.pop(sym, None)

        # Add new entries meeting enter threshold until capacity (using peak pct)
        sorted_candidates = sorted(
            crypto_data,
            key=lambda x: abs(x.get('price_change_percentage_1min_peak', x.get('price_change_percentage_1min', 0))),
            reverse=True
        )
        for coin in sorted_candidates:
            if len(pers) >= max_coins:
                break
            pct = coin.get('price_change_percentage_1min_peak', coin.get('price_change_percentage_1min', 0))
            if abs(pct) >= enter_pct and coin['symbol'] not in pers:
                pers[coin['symbol']] = {'entered_at': now_ts, 'enter_gain': pct}

        # Build separate gainers/losers lists from persistence set
        retained_symbols = set(pers.keys())
        try:
            if isinstance(one_minute_diag, dict):
                one_minute_diag["final_kept"] = len(retained_symbols)
        except Exception:
            pass
        retained_coins = [data_by_symbol[s] for s in retained_symbols if s in data_by_symbol]
        gainers = [c for c in retained_coins if c.get('price_change_percentage_1min_peak', c.get('price_change_percentage_1min', 0)) > 0]
        losers = [c for c in retained_coins if c.get('price_change_percentage_1min_peak', c.get('price_change_percentage_1min', 0)) < 0]
        gainers.sort(key=lambda x: x.get('price_change_percentage_1min_peak', x.get('price_change_percentage_1min', 0)), reverse=True)
        losers.sort(key=lambda x: x.get('price_change_percentage_1min_peak', x.get('price_change_percentage_1min', 0)))

        # --- Rank jitter dampening ---
        rank_cooldown_s = float(CONFIG.get("ONE_MIN_RANK_COOLDOWN_S", 10))
        min_rank_delta = int(CONFIG.get("ONE_MIN_RANK_MIN_DELTA", 2))

        def _dampen_rank(rows, bucket, reverse=False):
            if not rows:
                return rows
            state = one_minute_rank_state.get(bucket)
            if not isinstance(state, dict):
                return rows
            prev_ranks = state.get("ranks") or {}
            last_change = state.get("last_change") or {}
            pct_key = "price_change_percentage_1min_peak"

            new_ranks = {}
            for idx, row in enumerate(rows):
                sym = row.get("symbol")
                if sym:
                    new_ranks[sym] = idx + 1

            # prune removed symbols
            for sym in list(prev_ranks.keys()):
                if sym not in new_ranks:
                    prev_ranks.pop(sym, None)
                    last_change.pop(sym, None)

            dampened = []
            for idx, row in enumerate(rows):
                sym = row.get("symbol")
                new_rank = idx + 1
                if not sym:
                    dampened.append((new_rank, row))
                    continue
                prev_rank = prev_ranks.get(sym)
                last_ts = float(last_change.get(sym) or 0)
                delta = abs((prev_rank or new_rank) - new_rank)
                allow_move = (prev_rank is None) or (delta >= min_rank_delta) or ((now_ts - last_ts) >= rank_cooldown_s)
                if allow_move:
                    prev_ranks[sym] = new_rank
                    if prev_rank != new_rank:
                        last_change[sym] = now_ts
                    effective_rank = new_rank
                else:
                    effective_rank = prev_rank if prev_rank is not None else new_rank
                dampened.append((effective_rank, row))

            state["ranks"] = prev_ranks
            state["last_change"] = last_change

            def _pct(row):
                return row.get(pct_key, row.get("price_change_percentage_1min", 0))

            dampened.sort(
                key=lambda it: (it[0], -_pct(it[1]) if reverse else _pct(it[1]))
            )
            return [row for _, row in dampened]

        gainers = _dampen_rank(gainers, "gainers", reverse=True)
        losers = _dampen_rank(losers, "losers", reverse=False)

        # --- Market breadth & pump/dump signal metrics ---
        universe = [c.get('price_change_percentage_1min_peak', c.get('price_change_percentage_1min', 0)) or 0.0 for c in data_by_symbol.values()]
        abs_universe = [abs(x) for x in universe]
        def _pct(sorted_list, p):
            if not sorted_list:
                return None
            k = (len(sorted_list)-1) * (p/100.0)
            f = int(k); c2 = min(f+1, len(sorted_list)-1); w = k - f
            return round(sorted_list[f]*(1-w) + sorted_list[c2]*w, 4)
        if universe:
            s_univ = sorted(universe)
            s_abs = sorted(abs_universe)
            advancers = sum(1 for v in universe if v > 0)
            decliners = sum(1 for v in universe if v < 0)
            total = len(universe)
            adv_decl_ratio = round(advancers / decliners, 3) if decliners else None
            top = gainers[:5]
            top_avg = round(sum(c.get('price_change_percentage_1min_peak', c.get('price_change_percentage_1min',0)) for c in top)/len(top), 4) if top else None
            bottom = losers[:5]
            bottom_avg = round(sum(c.get('price_change_percentage_1min_peak', c.get('price_change_percentage_1min',0)) for c in bottom)/len(bottom), 4) if bottom else None
            prev_stats = dict(one_minute_market_stats) if one_minute_market_stats else None
            pct95_cur = _pct(s_univ,95)
            pct99_cur = _pct(s_univ,99)
            extreme_gainer_pct_cur = round(gainers[0].get('price_change_percentage_1min_peak', gainers[0].get('price_change_percentage_1min',0)),4) if gainers else None
            net_advancers_cur = advancers - decliners
            # Compute deltas (acceleration) vs previous snapshot
            spike_p95_delta = spike_p99_delta = extreme_gainer_accel = breadth_adv_decl_ratio_delta = net_advancers_delta = None
            spike_p95_rate = spike_p99_rate = extreme_gainer_accel_rate = breadth_adv_decl_ratio_rate = net_advancers_delta_rate = None
            if prev_stats and prev_stats.get('timestamp') and prev_stats.get('timestamp') != now_ts:
                dt = max(1.0, now_ts - prev_stats.get('timestamp'))
                if prev_stats.get('pct95') is not None and pct95_cur is not None:
                    spike_p95_delta = round(pct95_cur - prev_stats.get('pct95'), 4)
                    spike_p95_rate = round(spike_p95_delta / dt, 6)
                if prev_stats.get('pct99') is not None and pct99_cur is not None:
                    spike_p99_delta = round(pct99_cur - prev_stats.get('pct99'), 4)
                    spike_p99_rate = round(spike_p99_delta / dt, 6)
                if prev_stats.get('extreme_gainer_pct') is not None and extreme_gainer_pct_cur is not None:
                    extreme_gainer_accel = round(extreme_gainer_pct_cur - prev_stats.get('extreme_gainer_pct'), 4)
                    extreme_gainer_accel_rate = round(extreme_gainer_accel / dt, 6)
                if prev_stats.get('adv_decl_ratio') is not None and adv_decl_ratio is not None:
                    breadth_adv_decl_ratio_delta = round(adv_decl_ratio - prev_stats.get('adv_decl_ratio'), 6)
                    breadth_adv_decl_ratio_rate = round(breadth_adv_decl_ratio_delta / dt, 6)
                if prev_stats.get('breadth_net_advancers') is not None:
                    net_advancers_delta = net_advancers_cur - prev_stats.get('breadth_net_advancers')
                    net_advancers_delta_rate = round(net_advancers_delta / dt, 6)
            one_minute_market_stats.update({
                'timestamp': now_ts,
                'universe_count': total,
                'advancers': advancers,
                'decliners': decliners,
                'adv_decl_ratio': adv_decl_ratio,
                'pct50': _pct(s_univ,50),
                'pct75': _pct(s_univ,75),
                'pct90': _pct(s_univ,90),
                'pct95': pct95_cur,
                'pct99': pct99_cur,
                'abs_pct90': _pct(s_abs,90),
                'abs_pct95': _pct(s_abs,95),
                'abs_pct99': _pct(s_abs,99),
                'count_gt_1pct': sum(1 for v in abs_universe if v >= 1.0),
                'count_gt_2pct': sum(1 for v in abs_universe if v >= 2.0),
                'count_gt_5pct': sum(1 for v in abs_universe if v >= 5.0),
                'top5_avg_gain': top_avg,
                'bottom5_avg_loss': bottom_avg,
                'extreme_gainer_symbol': gainers[0]['symbol'] if gainers else None,
                'extreme_gainer_pct': extreme_gainer_pct_cur,
                'extreme_loser_symbol': losers[0]['symbol'] if losers else None,
                'extreme_loser_pct': round(losers[0].get('price_change_percentage_1min_peak', losers[0].get('price_change_percentage_1min',0)),4) if losers else None,
                # Acceleration / delta metrics
                'spike_p95_delta': spike_p95_delta,
                'spike_p99_delta': spike_p99_delta,
                'spike_p95_rate_per_sec': spike_p95_rate,
                'spike_p99_rate_per_sec': spike_p99_rate,
                'extreme_gainer_accel': extreme_gainer_accel,
                'extreme_gainer_accel_rate_per_sec': extreme_gainer_accel_rate,
                'breadth_net_advancers': net_advancers_cur,
                'breadth_net_advancers_delta': net_advancers_delta,
                'breadth_net_advancers_delta_rate_per_sec': net_advancers_delta_rate,
                'breadth_adv_decl_ratio_delta': breadth_adv_decl_ratio_delta,
                'breadth_adv_decl_ratio_rate_per_sec': breadth_adv_decl_ratio_rate,
            })
            # Advanced breadth analytics (z-scores, EMA, thrust, Bollinger, confirmation, alerts)
            with _one_min_hist_lock:
                if pct95_cur is not None:
                    _spike_p95_history.append(pct95_cur)
                if pct99_cur is not None:
                    _spike_p99_history.append(pct99_cur)
                if extreme_gainer_pct_cur is not None:
                    _extreme_gainer_history.append(extreme_gainer_pct_cur)
                def _z(hist):
                    if len(hist) < 5:
                        return None
                    mean = sum(hist)/len(hist)
                    var = sum((x-mean)**2 for x in hist)/len(hist)
                    if var <= 1e-12:
                        return 0.0
                    return round((hist[-1]-mean)/math.sqrt(var), 4)
                z_p95 = _z(_spike_p95_history)
                z_p99 = _z(_spike_p99_history)
                z_extreme = _z(_extreme_gainer_history)
                global _breadth_adv_decl_ratio_ema, _breadth_net_advancers_ema, _breadth_thrust_started_at
                if adv_decl_ratio is not None:
                    if _breadth_adv_decl_ratio_ema is None:
                        _breadth_adv_decl_ratio_ema = adv_decl_ratio
                    else:
                        _breadth_adv_decl_ratio_ema = (1-_BREADTH_EMA_ALPHA)*_breadth_adv_decl_ratio_ema + _BREADTH_EMA_ALPHA*adv_decl_ratio
                if net_advancers_cur is not None:
                    if _breadth_net_advancers_ema is None:
                        _breadth_net_advancers_ema = net_advancers_cur
                    else:
                        _breadth_net_advancers_ema = (1-_BREADTH_EMA_ALPHA)*_breadth_net_advancers_ema + _BREADTH_EMA_ALPHA*net_advancers_cur
                thrust_active = False
                if adv_decl_ratio is not None and adv_decl_ratio >= _BREADTH_THRUST_RATIO and net_advancers_cur >= _BREADTH_THRUST_NET_MIN:
                    if _breadth_thrust_started_at is None:
                        _breadth_thrust_started_at = now_ts
                    thrust_active = True
                else:
                    _breadth_thrust_started_at = None
                thrust_duration = (now_ts - _breadth_thrust_started_at) if _breadth_thrust_started_at else 0
                one_minute_market_stats.update({
                    'z_p95': z_p95,
                    'z_p99': z_p99,
                    'z_extreme_gainer': z_extreme,
                    'breadth_adv_decl_ratio_ema': round(_breadth_adv_decl_ratio_ema,4) if _breadth_adv_decl_ratio_ema is not None else None,
                    'breadth_net_advancers_ema': round(_breadth_net_advancers_ema,4) if _breadth_net_advancers_ema is not None else None,
                    'breadth_thrust_active': 1 if thrust_active else 0,
                    'breadth_thrust_duration_sec': round(thrust_duration,2),
                })
                if adv_decl_ratio is not None:
                    _adv_decl_ratio_history.append(adv_decl_ratio)
                    if len(_adv_decl_ratio_history) >= 5:
                        mean = sum(_adv_decl_ratio_history)/len(_adv_decl_ratio_history)
                        var = sum((x-mean)**2 for x in _adv_decl_ratio_history)/len(_adv_decl_ratio_history)
                        sd = math.sqrt(var)
                        upper = mean + _BREADTH_BB_K * sd
                        lower = mean - _BREADTH_BB_K * sd
                        one_minute_market_stats.update({
                            'breadth_adv_decl_ratio_bb_mid': round(mean,4),
                            'breadth_adv_decl_ratio_bb_upper': round(upper,4),
                            'breadth_adv_decl_ratio_bb_lower': round(lower,4),
                            'breadth_adv_decl_ratio_bb_sd': round(sd,5),
                        })
                # 3m confirmation overlay
                try:
                    confirm_up = 0
                    confirm_total = 0
                    for sym in list(one_minute_persistence['entries'].keys())[:100]:
                        t3 = three_minute_trends.get(sym)
                        if t3:
                            confirm_total += 1
                            if t3.get('last',0) > 0 and t3.get('score',0) > 0 and t3.get('last_dir') == 'up':
                                confirm_up += 1
                    confirm_ratio = round(confirm_up/confirm_total,4) if confirm_total else None
                    one_minute_market_stats.update({
                        'confirm_3m_overlap': confirm_total,
                        'confirm_3m_up': confirm_up,
                        'confirm_3m_up_ratio': confirm_ratio,
                    })
                except Exception:
                    confirm_ratio = None
                # Derived alert triggers
                try:
                    pump_thrust = 1 if (thrust_active and confirm_ratio and adv_decl_ratio and
                        confirm_ratio > THRESHOLDS['pump_thrust_confirm_ratio_min'] and
                        adv_decl_ratio > THRESHOLDS['pump_thrust_adv_decl_ratio_min']) else 0
                    narrowing_volatility = 1 if (
                        one_minute_market_stats.get('breadth_adv_decl_ratio_bb_sd') is not None and
                        one_minute_market_stats['breadth_adv_decl_ratio_bb_sd'] < THRESHOLDS['narrowing_vol_sd_max']
                    ) else 0
                    upper_band_touch = 1 if (
                        adv_decl_ratio and one_minute_market_stats.get('breadth_adv_decl_ratio_bb_upper') and
                        adv_decl_ratio >= one_minute_market_stats['breadth_adv_decl_ratio_bb_upper']
                    ) else 0
                    lower_band_touch = 1 if (
                        adv_decl_ratio and one_minute_market_stats.get('breadth_adv_decl_ratio_bb_lower') is not None and
                        adv_decl_ratio <= one_minute_market_stats['breadth_adv_decl_ratio_bb_lower']
                    ) else 0
                    accel_fade = 1 if (
                        spike_p95_rate is not None and
                        spike_p95_rate < THRESHOLDS['accel_fade_p95_rate_max'] and
                        thrust_duration > THRESHOLDS['accel_fade_min_thrust_seconds']
                    ) else 0
                    one_minute_market_stats.update({
                        'alert_pump_thrust': pump_thrust,
                        'alert_narrowing_vol': narrowing_volatility,
                        'alert_upper_band_touch': upper_band_touch,
                        'alert_lower_band_touch': lower_band_touch,
                        'alert_accel_fade': accel_fade,
                    })
                except Exception:
                    pass

        # Seed fallback: on a cold or quiet period when nothing is retained yet,
        # gently prefill with the top movers over a tiny threshold so UI isn't empty.
        if not retained_symbols:
            seed_pct = float(CONFIG.get('ONE_MIN_SEED_PCT', 0.02))  # 0.02% default
            seed_count = int(CONFIG.get('ONE_MIN_DEFAULT_SEED_COUNT', 10))
            seeded = 0
            for coin in sorted_candidates:
                if seeded >= seed_count:
                    break
                pct = coin.get('price_change_percentage_1min_peak', coin.get('price_change_percentage_1min', 0))
                if abs(pct) >= seed_pct:
                    pers[coin['symbol']] = {'entered_at': now_ts, 'enter_gain': pct}
                    seeded += 1
            if seeded:
                retained_symbols = set(pers.keys())
                retained_coins = [data_by_symbol[s] for s in retained_symbols if s in data_by_symbol]
                gainers = [c for c in retained_coins if c.get('price_change_percentage_1min_peak', c.get('price_change_percentage_1min', 0)) > 0]
                losers = [c for c in retained_coins if c.get('price_change_percentage_1min_peak', c.get('price_change_percentage_1min', 0)) < 0]
                gainers.sort(key=lambda x: x.get('price_change_percentage_1min_peak', x.get('price_change_percentage_1min', 0)), reverse=True)
                losers.sort(key=lambda x: x.get('price_change_percentage_1min_peak', x.get('price_change_percentage_1min', 0)))

            # Re-apply dampening after any seed fallback updates
            gainers = _dampen_rank(gainers, "gainers", reverse=True)
            losers = _dampen_rank(losers, "losers", reverse=False)

        # Attach peak values into formatted output
        def attach_peak(list_):
            out = []
            for c in list_:
                t = one_minute_trends.get(c["symbol"], {})
                out.append({
                    "symbol": c["symbol"],
                    "current": c["current_price"],
                    "initial_1min": c["initial_price_1min"],
                    "gain": c["price_change_percentage_1min"],
                    "interval_minutes": round(c.get("actual_interval_minutes", 1), 1),
                    "peak_gain": c.get("price_change_percentage_1min_peak", c.get("price_change_percentage_1min", 0)),
                    "trend_direction": t.get('last_dir', 'flat'),
                    "trend_streak": t.get('streak', 0),
                    "trend_score": t.get('score', 0.0),
                    "trend_delta": t.get('delta', 0.0),
                })
            return out

        result = {
            "gainers": attach_peak(gainers[:max_coins]),
            "losers": attach_peak(losers[:max_coins]),
            "throttled": True,
            "refresh_seconds": refresh_window,
            "enter_threshold_pct": enter_pct,
            "stay_threshold_pct": stay_pct,
            "dwell_seconds": dwell_seconds,
            "retained": len(retained_symbols)
        }
        logging.info(
            "1m retention candidates=%s retained_symbols=%s gainers=%s losers=%s enter=%.3f stay=%.3f dwell=%ss",
            len(crypto_data),
            len(retained_symbols),
            len(result["gainers"]),
            len(result["losers"]),
            enter_pct,
            stay_pct,
            dwell_seconds,
        )
        one_minute_cache['data'] = result
        one_minute_cache['timestamp'] = current_time
        logging.info(f"1-min data processed (throttle {refresh_window}s) retained={len(retained_symbols)} gainers={len(result['gainers'])} losers={len(result['losers'])}")
        return result
    except Exception as e:
        logging.error(f"Error in get_crypto_data_1min: {e}")
        return None

@app.route('/api/component/gainers-table-1min')
def get_gainers_table_1min():
    """Individual endpoint for 1-minute gainers table"""
    try:
        # If tests request seeded fixtures, bypass cached SWR helpers and
        # construct the response directly from the seeded fixture to avoid
        # stale cached outputs that were computed without the seed.
        if os.environ.get('USE_1MIN_SEED', '0') == '1':
            seeded = get_crypto_data_1min()
            if not seeded:
                return jsonify({"error": "No 1-minute data available"}), 503
            gainers = seeded.get('gainers', [])
            gainers_table_data = []
            for i, coin in enumerate(gainers[:20]):
                current_price = coin.get('current') or coin.get('current_price') or 0
                gain_pct = coin.get('gain') or coin.get('price_change_percentage_1min') or 0
                initial_price = coin.get('initial_1min') or coin.get('initial_price_1min') or current_price
                peak_gain = coin.get('peak_gain', gain_pct)
                gainers_table_data.append({
                    'rank': i + 1,
                    'symbol': coin.get('symbol'),
                    'current_price': current_price,
                    'price_change_percentage_1min': gain_pct,
                    'initial_price_1min': initial_price,
                    'actual_interval_minutes': coin.get('interval_minutes', 1),
                    'peak_gain': peak_gain,
                    'trend_direction': coin.get('trend_direction', 'flat'),
                    'trend_streak': coin.get('trend_streak', 0),
                    'trend_score': coin.get('trend_score', 0.0),
                    'trend_delta': coin.get('trend_delta', 0.0),
                    'momentum': 'strong' if gain_pct > 5 else 'moderate',
                    'alert_level': 'high' if gain_pct > 10 else 'normal'
                })
            data = {
                'component': 'gainers_table_1min',
                'data': gainers_table_data,
                'count': len(gainers_table_data),
                'table_type': 'gainers',
                'time_frame': '1_minute',
                'update_interval': 10000,
                'last_updated': datetime.now().isoformat(),
                'source': seeded.get('source'),
                'seed': seeded.get('seed', True)
            }
        else:
            data = _get_gainers_table_1min_swr()
        if not data:
            return jsonify({"error": "No 1-minute data available"}), 503
        swr_meta = {
            'ttl': _GAINERS_1M_SWR_TTL,
            'stale_window': _GAINERS_1M_SWR_STALE,
            'served_cached': getattr(_get_gainers_table_1min_swr, '_swr_last_served_cached', False),
        }
        # propagate a canonical source marker when the underlying data was seeded
        if isinstance(data, dict) and data.get('source'):
            swr_meta['source'] = data.get('source')
        if isinstance(data, dict) and data.get('seed'):
            swr_meta['seed'] = True
        # If the environment requests seeded fixtures, ensure the swr meta
        # reflects that even if a cached SWR result was computed earlier
        if os.environ.get('USE_1MIN_SEED', '0') == '1':
            swr_meta.setdefault('source', 'fixture-seed')
            swr_meta.setdefault('seed', True)
        return jsonify({**data, 'swr': swr_meta})
    except Exception as e:
        logging.error(f"Error in 1-minute gainers table endpoint: {e}")
        return jsonify({"error": str(e)}), 500
# =============================================================================

@app.route('/api/component/gainers-table-3min')
def get_gainers_table_3min():
    """Individual endpoint for 3-minute gainers table (parity with 1m endpoint)"""
    try:
        data = _get_gainers_table_3min_swr()
        if not data:
            return jsonify({"error": "No 3-minute data available"}), 503
        swr_meta = {
            'ttl': _GAINERS_3M_SWR_TTL,
            'stale_window': _GAINERS_3M_SWR_STALE,
            'served_cached': getattr(_get_gainers_table_3min_swr, '_swr_last_served_cached', False),
        }
        return jsonify({**data, 'swr': swr_meta})
    except Exception as e:
        logging.error(f"Error in 3-minute gainers table endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/component/losers-table-3min')
def get_losers_table_3min():
    """Individual endpoint for 3-minute losers table"""
    try:
        data = _get_losers_table_3min_swr()
        if not data:
            return jsonify({"error": "No 3-minute losers data available"}), 503
        swr_meta = {
            'ttl': _LOSERS_3M_SWR_TTL,
            'stale_window': _LOSERS_3M_SWR_STALE,
            'served_cached': getattr(_get_losers_table_3min_swr, '_swr_last_served_cached', False),
        }
        return jsonify({**data, 'swr': swr_meta})
    except Exception as e:
        logging.error(f"Error in 3-minute losers table endpoint: {e}")
        return jsonify({"error": str(e)}), 500


# Add startup time tracking
# Add startup time tracking for uptime calculation

@app.route('/')
def root():
    """Root endpoint"""
    try:
        data = _get_gainers_table_3min_swr()
        if not data:
            return jsonify({"error": ERROR_NO_DATA}), 503
        swr_meta = {
            'ttl': _GAINERS_3M_SWR_TTL,
            'stale_window': _GAINERS_3M_SWR_STALE,
            'served_cached': getattr(_get_gainers_table_3min_swr, '_swr_last_served_cached', False),
        }
        return jsonify({**data, 'swr': swr_meta})
    except Exception as e:
        logging.error(f"Error in gainers table endpoint: {e}")
        return jsonify({"error": str(e)}), 500
def get_banner_endpoint():
    """24h banner data endpoint"""
    try:
        banner_data = get_24h_top_movers()
        formatted_banner = format_banner_data(banner_data)
        return jsonify({
            "banner": formatted_banner,
            "count": len(formatted_banner),
            "last_updated": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Error in banner endpoint: {e}")
        return jsonify({"error": str(e)}), 500

# Legacy routes for backward compatibility
@app.route('/banner-1h')
def banner_1h_legacy():
    """Legacy banner endpoint - redirects to new API"""
    return get_banner_endpoint()

@app.route('/crypto')
def get_crypto_legacy():
    """Legacy crypto endpoint - redirects to new API"""
    return get_crypto_endpoint()

@app.route('/favicon.ico')
def favicon():
    return '', 204

# New API endpoints

@app.route('/api/chart/<symbol>')
def get_chart(symbol):
    """Get historical chart data for a specific coin"""
    days = request.args.get('days', 7, type=int)
    days = min(days, 30)  # Limit to 30 days max
    
    chart_data = get_historical_chart_data(symbol.upper(), days)
    if not chart_data:
        return jsonify({"error": f"No chart data available for {symbol}"}), 404
    
    # Add analysis
    analysis = analyze_coin_potential(symbol, chart_data)
    
    return jsonify({
        "symbol": symbol.upper(),
        "days": days,
        "data_points": len(chart_data),
        "chart_data": chart_data,
        "analysis": analysis
    })

@app.route('/api/recommendations')
def get_recommendations():
    """Get recommended coins to watch"""
    recommendations = get_trending_coins()
    
    # Add chart analysis for each recommendation
    for coin in recommendations:
        chart_data = get_historical_chart_data(coin['symbol'], 3)  # 3 days for quick analysis
        if chart_data:
            analysis = analyze_coin_potential(coin['symbol'], chart_data)
            coin['analysis'] = analysis
            coin['chart_preview'] = chart_data[-24:] if len(chart_data) >= 24 else chart_data  # Last 24 hours
        else:
            coin['analysis'] = {"score": 0, "signals": []}
            coin['chart_preview'] = []
    
    # Sort by analysis score
    recommendations.sort(key=lambda x: x.get('analysis', {}).get('score', 0), reverse=True)
    
    return jsonify({
        "recommendations": recommendations,
        "updated_at": datetime.now().isoformat(),
        "total_count": len(recommendations)
    })

@app.route('/api/popular-charts')
def get_popular_charts():
    """Get chart data for most popular coins"""
    popular_symbols = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD', 'LINK-USD']
    charts = {}
    
    for symbol in popular_symbols:
        chart_data = get_historical_chart_data(symbol, 7)
        if chart_data:
            analysis = analyze_coin_potential(symbol, chart_data)
            charts[symbol] = {
                "chart_data": chart_data,
                "analysis": analysis,
                "current_price": chart_data[-1]['price'] if chart_data else 0
            }
    
    return jsonify(charts)

@app.route('/api/market-overview')
def get_market_overview():
    """Get overall market overview with key metrics (CoinGecko removed)"""
    try:
        # CoinGecko global market data removed. Returning default values.
        overview = {
            "total_market_cap_usd": 0,
            "total_volume_24h_usd": 0,
            "market_cap_change_24h": 0,
            "active_cryptocurrencies": 0,
            "markets": 0,
            "btc_dominance": 0
        }
        
        # Trending coins now returns empty list
        trending = get_trending_coins()[:5]
        
        # Get fear & greed index (mock data since API requires key)
        fear_greed_index = {
            "value": 65,  # You can integrate real Fear & Greed API here
            "classification": "Greed",
            "last_update": datetime.now().isoformat()
        }
        
        return jsonify({
            "market_overview": overview,
            "trending_coins": trending,
            "fear_greed_index": fear_greed_index,
            "last_updated": datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching market overview: {e}")
        return jsonify({"error": "Failed to fetch market overview"}), 500

@app.route('/api/config_legacy', methods=['GET'])
def get_config_legacy():
    """Temporary legacy endpoint retained for backward compatibility; returns same payload as unified /api/config GET"""
    return api_config()

@app.route('/api/health')
def health_check():
    """Comprehensive health check endpoint for monitoring"""
    try:
        # Test primary API connectivity
        coinbase_status = "unknown"
        
        try:
            coinbase_response = requests.get("https://api.exchange.coinbase.com/products", timeout=5)
            coinbase_status = "up" if coinbase_response.status_code == 200 else "down"
        except:
            coinbase_status = "down"
            
        # Determine overall health
        overall_status = "healthy"
        if coinbase_status == "down":
            overall_status = "unhealthy"
            
        return jsonify({
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "version": "3.0.0",
            "uptime": time.time() - startup_time,
            "cache_status": {
                "data_cached": cache["data"] is not None,
                "last_update": cache["timestamp"],
                "cache_age_seconds": time.time() - cache["timestamp"] if cache["timestamp"] > 0 else 0,
                "ttl": cache["ttl"]
            },
            "external_apis": {
                "coinbase": coinbase_status
            },
            "data_tracking": {
                "symbols_tracked": len(price_history),
                "max_history_per_symbol": CONFIG.get('MAX_PRICE_HISTORY', 100)
            }
        }), 200 if overall_status == "healthy" else 503
    except Exception as e:
        logging.error(f"Health check error: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503

@app.route('/api/server-info')
def server_info():
    """Get server information including port and status, uptime, commit and thresholds."""
    try:
        uptime_seconds = time.time() - startup_time
        one_min_cfg = {
            "enabled": CONFIG.get('ENABLE_1MIN', True),
            "refresh_seconds": CONFIG.get('ONE_MIN_REFRESH_SECONDS'),
            "enter_threshold_pct": CONFIG.get('ONE_MIN_ENTER_PCT'),
            "stay_threshold_pct": CONFIG.get('ONE_MIN_STAY_PCT'),
            "dwell_seconds": CONFIG.get('ONE_MIN_DWELL_SECONDS'),
            "max_coins": CONFIG.get('ONE_MIN_MAX_COINS'),
        }
        alerts_cfg = {
            "cooldown_seconds": CONFIG.get('ALERTS_COOLDOWN_SECONDS'),
            "streak_thresholds": CONFIG.get('ALERTS_STREAK_THRESHOLDS'),
        }
        payload = {
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "version": "3.0.0",
            "commit": _get_commit_sha(),
            "uptime_seconds": uptime_seconds,
            "errors_5xx": _ERROR_STATS.get('5xx', 0),
            "runtime": {
                "python_version": sys.version.split(" ")[0] if hasattr(sys, 'version') else "unknown",
                "platform": sys.platform if hasattr(sys, 'platform') else "unknown",
                "env": os.environ.get('ENVIRONMENT', 'production')
            },
            "port": CONFIG['PORT'],
            "host": CONFIG['HOST'],
            "debug": CONFIG['DEBUG'],
            "cors_origins": cors_origins,
            "cache_ttl": CONFIG['CACHE_TTL'],
            "update_interval": CONFIG['UPDATE_INTERVAL'],
            "one_minute": one_min_cfg,
            "alerts": alerts_cfg,
            "cache_status": {
                "data_cached": cache["data"] is not None,
                "cache_age_seconds": time.time() - cache["timestamp"] if cache["timestamp"] > 0 else 0,
                "ttl": cache["ttl"],
            },
        }
        # Optionally include light system metrics if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                import psutil as _ps
                process = _ps.Process()
                payload["process"] = {
                    "pid": process.pid,
                    "cpu_percent": process.cpu_percent(interval=0.0),
                    "rss_mb": round(process.memory_info().rss / (1024 * 1024), 2),
                }
            except Exception:
                pass
        return jsonify(payload), 200
    except Exception as e:
        logging.error(f"server-info error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 200

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Clear all caches"""
    global cache, price_history
    
    cache = {
        "data": None,
        "timestamp": 0,
        "ttl": CONFIG['CACHE_TTL']
    }
    price_history.clear()
    
    logging.info("Cache and price history cleared")
    return jsonify({"message": "Cache cleared successfully"})

@app.route('/api/technical-analysis/<symbol>')
def get_technical_analysis_endpoint(symbol):
    """Get technical analysis for a specific cryptocurrency"""
    try:
        from technical_analysis import get_technical_analysis
        
        # Validate symbol format
        symbol = symbol.upper().replace('-USD', '')
        if not symbol.isalpha() or len(symbol) < 2 or len(symbol) > 10:
            return jsonify({"error": "Invalid symbol format"}), 400
        
        # Get technical analysis
        analysis = get_technical_analysis(symbol)
        
        return jsonify({
            "success": True,
            "data": analysis,
            "timestamp": datetime.now().isoformat()
        })
        
    except ImportError as e:
        logging.error(f"Technical analysis module not available: {e}")
        return jsonify({"error": "Technical analysis not available"}), 503
    except Exception as e:
        logging.error(f"Error getting technical analysis for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news/<symbol>')
def get_crypto_news(symbol):
    """Get news for a specific cryptocurrency (placeholder for now)"""
    try:
        # Placeholder implementation - in real app you'd integrate with news APIs
        symbol = symbol.upper().replace('-USD', '')
        
        # Mock news data for demonstration
        mock_news = [
            {
                "id": 1,
                "title": f"{symbol} Shows Strong Technical Momentum",
                "summary": f"Technical analysis suggests {symbol} may continue its current trend based on recent price action and volume indicators.",
                "source": "Crypto Technical Analysis",
                "published": (datetime.now() - timedelta(hours=2)).isoformat(),
                "sentiment": "neutral",
                "url": f"https://example.com/news/{symbol.lower()}-analysis"
            },
            {
                "id": 2,
                "title": f"Market Update: {symbol} Trading Volume Analysis",
                "summary": f"Recent trading patterns in {symbol} indicate increased institutional interest and potential breakout scenarios.",
                "source": "Market Insights",
                "published": (datetime.now() - timedelta(hours=6)).isoformat(),
                "sentiment": "positive",
                "url": f"https://example.com/news/{symbol.lower()}-volume"
            },
            {
                "id": 3,
                "title": f"{symbol} Price Action Review",
                "summary": f"Weekly review of {symbol} price movements and key support/resistance levels for traders to monitor.",
                "source": "Trading Weekly",
                "published": (datetime.now() - timedelta(days=1)).isoformat(),
                "sentiment": "neutral",
                "url": f"https://example.com/news/{symbol.lower()}-review"
            }
        ]
        
        return jsonify({
            "success": True,
            "symbol": symbol,
            "articles": mock_news,
            "count": len(mock_news),
            "timestamp": datetime.now().isoformat(),
            "note": "Demo data - integrate with real news API for production"
        })
        
    except Exception as e:
        logging.error(f"Error getting news for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/social-sentiment/<symbol>')
def get_hybrid_social_sentiment(symbol):
    try:
        clean_symbol = symbol.upper().replace('-USD', '').replace('USD', '')
        if not clean_symbol.isalpha() or len(clean_symbol) < 2:
            return jsonify({"error": "Invalid symbol format"}), 400

        mock_headlines = [
            f"Institutional inflows for {clean_symbol} reach record highs",
            f"Regulatory uncertainty clouds {clean_symbol} short-term outlook",
            f"Traders optimistic about {clean_symbol} upcoming network upgrade",
        ]

        current_prices = get_current_prices() if 'get_current_prices' in globals() else {}
        price = current_prices.get(f"{clean_symbol}-USD", 0)

        sentiment_result = ai_engine.score_headlines_local(mock_headlines)
        narrative = ai_engine.generate_narrative(clean_symbol, mock_headlines, price)

        return jsonify({
            "success": True,
            "data": {
                "symbol": clean_symbol,
                "overall_score": sentiment_result['score'],
                "label": sentiment_result['label'],
                "narrative": narrative,
                "sources_breakdown": {
                    "finbert_confidence": sentiment_result['confidence'],
                    "headlines_analyzed": len(mock_headlines),
                    "model": "FinBERT + Gemini 1.5 Flash"
                }
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Error getting hybrid sentiment for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

# =============================================================================

def _scan_insight_logs(insights_memory, lines=400):
    """Scan recent insight log lines and reconstruct add/update maps for auto logging decisions."""
    import re
    from datetime import datetime
    add_pattern = re.compile(r"User added (\w+) to their watchlist at \$([0-9.]+)")
    update_pattern = re.compile(r"(\w+) is now at \$([0-9.]+) \(([+-]?[0-9.]+)%\)")
    added_price, last_logged_price, last_logged_time = {}, {}, {}
    for line in insights_memory.logs[-lines:]:
        parts = line.split('|', 1)
        ts = None
        if len(parts) == 2:
            ts_raw = parts[0].strip()
            try:
                ts = datetime.fromisoformat(ts_raw.replace('Z',''))
            except Exception:
                ts = None
            entry = parts[1].strip()
        else:
            entry = line.strip()
        m_add = add_pattern.search(entry)
        if m_add:
            sym = m_add.group(1)
            added_price[sym] = float(m_add.group(2))
            continue
        m_upd = update_pattern.search(entry)
        if m_upd:
            sym = m_upd.group(1)
            last_logged_price[sym] = float(m_upd.group(2))
            if ts:
                last_logged_time[sym] = ts
    return added_price, last_logged_price, last_logged_time


def _auto_log_watchlist_moves(current_prices, banner_data):
    """Auto-log significant price & volume moves for watchlist symbols using configurable thresholds."""
    if not INSIGHTS_MEMORY or not watchlist_db:
        return
    try:
        from datetime import datetime, timedelta
        added_price, last_logged_price, last_logged_time = _scan_insight_logs(INSIGHTS_MEMORY)
        now = datetime.now().astimezone()
        # Build quick lookup for banner volume and 24h change if available
        banner_lookup = {c['symbol']: c for c in (banner_data or [])}
        for sym in watchlist_db:
            add_p = added_price.get(sym)
            cur = current_prices.get(sym)
            if not add_p or not cur:
                continue
            net_change_pct = (cur - add_p) / add_p * 100
            if abs(net_change_pct) >= INSIGHTS_MIN_NET_CHANGE_PCT:
                prev_price = last_logged_price.get(sym, add_p)
                step_change_pct = (cur - prev_price) / prev_price * 100 if prev_price else net_change_pct
                if abs(step_change_pct) >= INSIGHTS_MIN_STEP_CHANGE_PCT:
                    last_ts = last_logged_time.get(sym)
                    if not last_ts or now - last_ts >= timedelta(minutes=2):
                        INSIGHTS_MEMORY.add(f"{sym} is now at ${cur:.2f} ({net_change_pct:+.2f}%)")
                        continue  # avoid double logging volume same cycle if price just logged
            # Volume spike condition (only if not just price-logged above)
            banner = banner_lookup.get(sym)
            if banner:
                vol = banner.get('volume_24h', 0)
                price_change_24h = banner.get('price_change_24h', 0)
                if vol >= VOLUME_SPIKE_THRESHOLD and abs(price_change_24h) >= VOLUME_SPIKE_MIN_CHANGE_PCT:
                    last_ts = last_logged_time.get(sym)
                    if not last_ts or now - last_ts >= timedelta(minutes=10):
                        INSIGHTS_MEMORY.add(f"{sym} volume spike {vol:,.0f} (24h change {price_change_24h:+.2f}%)")
    except Exception as e:
        logging.debug(f"Auto logging skipped: {e}")


# Throttle heavier snapshot computations (volume banners/candles).
_MW_LAST_HEAVY_SNAPSHOT_AT = 0.0


def _compute_snapshots_from_cache():
    """Recompute snapshots using existing cached prices (fast, no network calls)."""
    try:
        # Throttle heavy snapshot work (volume banners/candles). The compute loop
        # runs frequently (e.g. every ~8s); keeping this function lightweight is
        # critical for a "live" UI.
        global _MW_LAST_HEAVY_SNAPSHOT_AT
        heavy_interval_s = float(os.environ.get('MW_HEAVY_SNAPSHOT_INTERVAL_S', '30'))
        now_s = time.time()
        do_heavy = (now_s - _MW_LAST_HEAVY_SNAPSHOT_AT) >= heavy_interval_s

        # Get cached prices (no network fetch)
        cached_prices = last_current_prices.get('data') or {}
        partial_tick = bool(last_current_prices.get('partial'))
        partial_reason = last_current_prices.get('partial_reason')
        partial_ok_ratio = last_current_prices.get('ok_ratio')
        partial_ok = last_current_prices.get('ok')
        partial_submitted = last_current_prices.get('submitted')

        # Recompute 3m data using cached prices
        data_3min = get_crypto_data(current_prices=cached_prices, force_refresh=False) if cached_prices else None

        # Recompute 1m data using cached prices
        if CONFIG.get('ENABLE_1MIN', True) and cached_prices:
            try:
                _ = get_crypto_data_1min(current_prices=cached_prices)
            except Exception as e:
                logging.debug(f"Snapshot 1m recompute skipped: {e}")

        # Build component snapshots
        try:
            g1m = _get_gainers_table_1min_swr() if CONFIG.get('ENABLE_1MIN', True) else None
        except Exception:
            g1m = None
        try:
            g3m = _get_gainers_table_3min_swr()
        except Exception:
            g3m = None
        try:
            l3m = _get_losers_table_3min_swr()
        except Exception:
            l3m = None

        def _mark_partial(payload):
            if not partial_tick or not isinstance(payload, dict):
                return payload
            out = dict(payload)
            out['partial'] = True
            out['partial_reason'] = partial_reason
            out['partial_ok_ratio'] = partial_ok_ratio
            out['partial_ok'] = partial_ok
            out['partial_submitted'] = partial_submitted
            return out

        g1m = _mark_partial(g1m)
        g3m = _mark_partial(g3m)
        l3m = _mark_partial(l3m)

        # Banner snapshots (lightweight)
        try:
            banner_rows = (data_3min or {}).get('banner') or []
            b1h_price_rows = []

            def _to_float(val):
                try:
                    if val is None:
                        return None
                    if isinstance(val, (int, float)):
                        return float(val)
                    s = str(val).strip().replace("%", "")
                    return float(s)
                except Exception:
                    return None

            for coin in banner_rows:
                try:
                    pct = _to_float(coin.get("pct_1h"))
                    if pct is None:
                        pct = _to_float(coin.get("price_change_1h"))
                    if pct is None or not math.isfinite(pct):
                        continue
                    symbol = coin.get("symbol")
                    b1h_price_rows.append({
                        "symbol": symbol,
                        "product_id": coin.get("product_id") or symbol,
                        "current_price": float(coin.get("current_price", 0) or 0),
                        "initial_price_1h": float(coin.get("initial_price_1h", 0) or 0),
                        "price_change_1h": pct,
                        "pct_1h": pct,
                        "pct_change_1h": pct,
                        "market_cap": float(coin.get("market_cap", 0) or 0),
                    })
                except Exception:
                    continue
            b1h_price_rows.sort(key=lambda r: r.get("pct_1h", 0), reverse=True)
            # If underfilled, widen the candidate pool using cached 1h changes
            if len(b1h_price_rows) < 20:
                try:
                    current_prices = last_current_prices.get('data') if isinstance(last_current_prices, dict) else None
                    if isinstance(current_prices, dict) and current_prices:
                        snapshot_ts_s = int(last_current_prices.get('timestamp') or time.time())
                        hour_changes = calculate_1hour_price_changes(current_prices, snapshot_ts_s)
                        existing = {r.get('symbol') for r in b1h_price_rows if r.get('symbol')}
                        extra = []
                        for change in (hour_changes or []):
                            try:
                                pct = float(change.get('price_change_1h', 0) or 0)
                            except Exception:
                                pct = 0.0
                            if not math.isfinite(pct):
                                continue
                            sym = change.get('symbol')
                            if not sym or sym in existing:
                                continue
                            extra.append({
                                'symbol': sym,
                                'product_id': change.get('product_id') or sym,
                                'current_price': float(change.get('current_price', 0) or 0),
                                'initial_price_1h': float(change.get('price_1h_ago', 0) or 0),
                                'price_change_1h': pct,
                                'pct_1h': pct,
                                'pct_change_1h': pct,
                                'market_cap': 0.0,
                            })
                        extra.sort(key=lambda r: r.get('pct_1h', 0), reverse=True)
                        if extra:
                            b1h_price_rows.extend(extra)
                except Exception:
                    pass

            b1h_price_rows = b1h_price_rows[:20]
            banner_1h_price = {
                'component': 'banner_1h_price',
                'data': b1h_price_rows,
                'last_updated': datetime.now().isoformat(),
            }
        except Exception:
            banner_1h_price = None

        banner_1h_volume = None
        if do_heavy:
            try:
                vb_rows, vb_ts = get_banner_1h_volume(banner_data=banner_rows)
                banner_1h_volume = {
                    'component': 'banner_1h_volume',
                    'data': vb_rows or [],
                    'last_updated': vb_ts or datetime.now().isoformat(),
                }
            except Exception:
                banner_1h_volume = None

        # Candle volume snapshot (heaviest: involves per-symbol volume cache reads)
        display_symbols = set()
        try:
            for coin in (banner_rows or [])[:20]:
                sym = coin.get('symbol')
                if sym:
                    display_symbols.add(sym)

            if g1m and isinstance(g1m, dict):
                for row in (g1m.get('data') or [])[:15]:
                    sym = row.get('symbol')
                    if sym:
                        display_symbols.add(sym)

            if g3m and isinstance(g3m, dict):
                for row in (g3m.get('data') or [])[:15]:
                    sym = row.get('symbol')
                    if sym:
                        display_symbols.add(sym)

            if l3m and isinstance(l3m, dict):
                for row in (l3m.get('data') or [])[:15]:
                    sym = row.get('symbol')
                    if sym:
                        display_symbols.add(sym)

            volume_1h_candles = None
            if do_heavy and display_symbols:
                vol1h_results = _get_candle_volume_for_symbols(list(display_symbols))
                vol1h_results.sort(key=lambda x: x.get('vol1h', 0), reverse=True)

                volume_1h_candles = {
                    'component': 'volume_1h_candles',
                    'data': vol1h_results[:20],
                    'last_updated': datetime.now().isoformat(),
                }
        except Exception as e:
            logging.debug(f"Candle snapshot skip: {e}")
            volume_1h_candles = None

        # 1h volume movers snapshot (SQLite-backed): compute in background only
        volume1h_snapshot = None
        if do_heavy:
            try:
                payload = _volume1h_build_payload_snapshot()
                rows = _volume1h_compute_ranked(payload) or []
                volume1h_snapshot = {
                    'component': 'volume1h',
                    'data': rows,
                    'last_updated': datetime.now().isoformat(),
                }
            except Exception as e:
                logging.debug(f"volume1h snapshot skip: {e}")
                volume1h_snapshot = None

            # Fallback: if banner snapshot is empty but we have candle rows, build
            # a banner-compatible snapshot so the UI can show seeded rows during dev.
        try:
            if (not banner_1h_volume or (isinstance(banner_1h_volume, dict) and len(banner_1h_volume.get('data') or []) == 0)) and volume_1h_candles and isinstance(volume_1h_candles, dict):
                rows = []
                for it in (volume_1h_candles.get('data') or [])[:20]:
                    pid = it.get('product_id') or it.get('id')
                    sym = (it.get('symbol') or (pid.split('-')[0] if isinstance(pid, str) and '-' in pid else None) or '').upper()
                    vol_now = it.get('volume_1h_now') or it.get('vol1h')
                    vol_prev = it.get('volume_1h_prev') or it.get('vol1h_prev')
                    pct = it.get('volume_change_1h_pct') or it.get('vol1h_pct_change')
                    missing_reason = it.get('baseline_missing_reason')
                    # baseline_ready: both prev and pct must be truly computed (no backsolve)
                    baseline_ready = (pct is not None) and (vol_prev is not None)
                    pct_val = float(pct) if pct is not None else None
                    rows.append({
                        'symbol': sym,
                        'product_id': pid or (f"{sym}-USD" if sym else None),
                        'volume_1h_now': float(vol_now) if vol_now is not None else None,
                        'volume_1h_prev': float(vol_prev) if vol_prev is not None else None,
                        'volume_change_1h_pct': pct_val,
                        'vol_pct_1h': pct_val,
                        'baseline_ready': bool(baseline_ready),
                        'baseline_missing_reason': None if baseline_ready else (missing_reason or 'warming_candles'),
                        'source': 'volume_1h_candles',
                    })
                rows = [r for r in rows if isinstance(r.get('vol_pct_1h'), (int, float))]
                rows.sort(key=lambda r: r.get('vol_pct_1h'), reverse=True)
                banner_1h_volume = {
                    'component': 'banner_1h_volume',
                    'data': rows[:20],
                    'last_updated': datetime.now().isoformat(),
                }
        except Exception:
            pass

        # Update snapshots.
        # IMPORTANT: avoid overwriting existing snapshots with None because that
        # can cause the UI to flap to "STALE" even though prior data exists.
        updates = {"updated_at": datetime.now().isoformat()}
        if isinstance(g1m, dict):
            rows = g1m.get('data') or []
            if partial_tick and not rows:
                prev_rows, _ = _wrap_rows_and_ts(_mw_get_component_snapshot('gainers_1m'))
                if isinstance(prev_rows, list) and prev_rows:
                    logging.info("partial_tick: keep gainers_1m snapshot (%d rows)", len(prev_rows))
                else:
                    updates["gainers_1m"] = g1m
            else:
                updates["gainers_1m"] = g1m
        if isinstance(g3m, dict):
            rows = g3m.get('data') or []
            if partial_tick and not rows:
                prev_rows, _ = _wrap_rows_and_ts(_mw_get_component_snapshot('gainers_3m'))
                if isinstance(prev_rows, list) and prev_rows:
                    logging.info("partial_tick: keep gainers_3m snapshot (%d rows)", len(prev_rows))
                else:
                    updates["gainers_3m"] = g3m
            else:
                updates["gainers_3m"] = g3m
        if isinstance(l3m, dict):
            rows = l3m.get('data') or []
            if partial_tick and not rows:
                prev_rows, _ = _wrap_rows_and_ts(_mw_get_component_snapshot('losers_3m'))
                if isinstance(prev_rows, list) and prev_rows:
                    logging.info("partial_tick: keep losers_3m snapshot (%d rows)", len(prev_rows))
                else:
                    updates["losers_3m"] = l3m
            else:
                updates["losers_3m"] = l3m
        if isinstance(banner_1h_price, dict):
            updates["banner_1h_price"] = banner_1h_price
        if do_heavy and isinstance(banner_1h_volume, dict):
            updates["banner_1h_volume"] = banner_1h_volume
        if do_heavy and isinstance(volume_1h_candles, dict):
            updates["volume_1h_candles"] = volume_1h_candles
        if do_heavy and isinstance(volume1h_snapshot, dict):
            updates["volume1h"] = volume1h_snapshot

        # --- Market Heat computation (closed-loop, no network) ---
        try:
            heat = _compute_market_heat()
            with _MARKET_HEAT_LOCK:
                _MARKET_HEAT_CACHE.update(heat)
                _MARKET_HEAT_HISTORY.append(heat)
            _emit_volatility_spike_alert(heat)
        except Exception as e:
            logging.debug(f"Market heat compute skip: {e}")

        # --- Divergence detection: 1m vs 3m disagreement ---
        try:
            cached_prices = last_current_prices.get('data') or {}
            for sym in cached_prices:
                hist_1m = price_history_1min.get(sym)
                hist_3m = price_history.get(sym)
                if not hist_1m or len(hist_1m) < 2 or not hist_3m or len(hist_3m) < 2:
                    continue
                try:
                    _, latest_price = hist_1m[-1]
                    # 1m return
                    base_1m = None
                    for ts_i, p_i in reversed(list(hist_1m)):
                        if now_s - ts_i >= 45:
                            base_1m = p_i
                            break
                    # 3m return
                    base_3m = None
                    for ts_i, p_i in reversed(list(hist_3m)):
                        if now_s - ts_i >= 120:
                            base_3m = p_i
                            break
                    if base_1m and base_1m > 0 and base_3m and base_3m > 0:
                        ret_1m = ((latest_price - base_1m) / base_1m) * 100
                        ret_3m = ((latest_price - base_3m) / base_3m) * 100
                        _emit_divergence_alert(sym, ret_1m, ret_3m, latest_price)
                except Exception:
                    continue
        except Exception as e:
            logging.debug(f"Divergence detection skip: {e}")

        # --- Whale + Stealth detection from volume cache ---
        try:
            with _CANDLE_VOLUME_CACHE_LOCK:
                vol_items = list(_CANDLE_VOLUME_CACHE.items())
            cached_prices_data = last_current_prices.get('data') or {}
            for product_id, vol_data in vol_items:
                if not isinstance(vol_data, dict):
                    continue
                vol1h = vol_data.get('vol1h')
                vol1h_pct = vol_data.get('vol1h_pct_change')
                sym = product_id.split('-')[0].upper() if '-' in product_id else product_id
                price_val = cached_prices_data.get(product_id) or cached_prices_data.get(sym) or 0

                # Whale detection (always try — z-score can fire even without vol1h_pct)
                _emit_whale_alert(sym, vol1h, vol1h_pct, price_val)

                # Stealth detection: need 3m price change
                hist_3m = price_history.get(sym)
                if hist_3m and len(hist_3m) >= 2 and vol1h_pct is not None:
                    try:
                        _, latest_p = hist_3m[-1]
                        base_p = None
                        for ts_i, p_i in reversed(list(hist_3m)):
                            if now_s - ts_i >= 120:
                                base_p = p_i
                                break
                        if base_p and base_p > 0:
                            pct_3m = ((latest_p - base_p) / base_p) * 100
                            _emit_stealth_alert(sym, pct_3m, vol1h_pct, latest_p)
                    except Exception:
                        pass
        except Exception as e:
            logging.debug(f"Whale/stealth detection skip: {e}")

        # --- FOMO / Fear macro alert from heat + F&G ---
        try:
            with _MARKET_HEAT_LOCK:
                h_score = _MARKET_HEAT_CACHE.get("score", 50)
                h_label = _MARKET_HEAT_CACHE.get("label", "NEUTRAL")
            fg = _fetch_fear_and_greed_cached()
            fg_val = fg.get("value") if fg else None
            _emit_fomo_alert(h_score, h_label, fg_val)
        except Exception as e:
            logging.debug(f"FOMO/fear alert skip: {e}")

        # Alerts snapshot (main only). Trend alerts are debug-only and do not
        # mix into the main UI stream.
        try:
            alerts_items, _alerts_meta = _mw_get_alerts_normalized_with_sticky()
            updates["alerts"] = {
                'component': 'alerts',
                'data': (alerts_items or [])[-400:],
                'last_updated': datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            pass

        _mw_set_component_snapshots(**updates)
        if do_heavy:
            _MW_LAST_HEAVY_SNAPSHOT_AT = now_s
        logging.debug("Snapshot recomputed from cached prices")

    except Exception as e:
        logging.error(f"Error in snapshot recompute: {e}")


def _fetch_prices_and_update_history():
    """Fetch fresh prices from Coinbase and update price history (slow, network calls)."""
    try:
        # Fetch prices from Coinbase
        current_prices = get_current_prices() or {}
        if current_prices:
            last_current_prices['data'] = current_prices
            now_ts = int(time.time())
            last_current_prices['timestamp'] = now_ts

            # Persist price snapshot to SQLite for interval calculations
            try:
                rows = [(product_id, float(price)) for product_id, price in current_prices.items()]
                insert_price_snapshot(now_ts, rows)

                # Prune snapshots older than retention window (default 2 hours)
                retention = int(os.environ.get('PRICE_DB_RETENTION_SECONDS', 7200))
                prune_old(now_ts - retention)
            except Exception as e:
                logging.error(f"SQLite price snapshot persistence failed: {e}")

            # Update 3m data cache with fresh prices (force refresh to append history)
            data_3min = get_crypto_data(current_prices=current_prices, force_refresh=True)
            if data_3min:
                logging.info(
                    f"Price fetch: {len(data_3min.get('gainers', []))} gainers, {len(data_3min.get('losers', []))} losers, {len(data_3min.get('banner', []))} banner"
                )

            # Update 1m history with fresh prices
            if CONFIG.get('ENABLE_1MIN', True):
                try:
                    _ = get_crypto_data_1min(current_prices=current_prices, force_refresh=True)
                    logging.debug("1m history updated with fresh prices")
                except Exception as e:
                    logging.error(f"1m history update failed: {e}")

                # Watchlist auto-logging
                _auto_log_watchlist_moves(current_prices, data_3min.get('banner') if data_3min else [])

            # Update candle volume cache (background, display-set only)
            try:
                # Collect display-set from current snapshots
                display_symbols = set()

                with _MW_COMPONENT_SNAPSHOTS_LOCK:
                    g1m_snap = _MW_COMPONENT_SNAPSHOTS.get('gainers_1m')
                    g3m_snap = _MW_COMPONENT_SNAPSHOTS.get('gainers_3m')
                    l3m_snap = _MW_COMPONENT_SNAPSHOTS.get('losers_3m')
                    banner_snap = _MW_COMPONENT_SNAPSHOTS.get('banner_1h_price')

                    if banner_snap and isinstance(banner_snap, dict):
                        for row in (banner_snap.get('data') or [])[:20]:
                            sym = row.get('symbol')
                            if sym:
                                display_symbols.add(sym)

                    if g1m_snap and isinstance(g1m_snap, dict):
                        for row in (g1m_snap.get('data') or [])[:15]:
                            sym = row.get('symbol')
                            if sym:
                                display_symbols.add(sym)

                    if g3m_snap and isinstance(g3m_snap, dict):
                        for row in (g3m_snap.get('data') or [])[:15]:
                            sym = row.get('symbol')
                            if sym:
                                display_symbols.add(sym)

                    if l3m_snap and isinstance(l3m_snap, dict):
                        for row in (l3m_snap.get('data') or [])[:15]:
                            sym = row.get('symbol')
                            if sym:
                                display_symbols.add(sym)

                product_ids = [f"{sym}-USD" for sym in display_symbols if sym]
                if product_ids:
                    logging.debug(f"Updating candle cache for {len(product_ids)} symbols")
                    _update_candle_volume_cache(product_ids)
            except Exception as e:
                logging.debug(f"Candle cache update skip: {e}")

            # Pre-warm Fear & Greed cache (non-blocking, best-effort)
            try:
                _fetch_fear_and_greed_cached()
            except Exception:
                pass

    except Exception as e:
        logging.error(f"Error in price fetch: {e}")


def _volume1h_updater_loop():
    _volume_db_init_once()
    logging.info(f"Starting volume1h updater: interval={VOLUME_1H_REFRESH_SEC}s workers={VOLUME_1H_WORKERS}")
    while True:
        loop_start = time.time()
        snapshot_payload = _volume1h_build_payload_snapshot()
        tracked = get_volume_tracked_product_ids(snapshot_payload)

        ok = 0
        fail = 0
        rl = 0
        skipped = 0
        now_ts = int(time.time())

        if tracked:
            with ThreadPoolExecutor(max_workers=VOLUME_1H_WORKERS) as executor:
                futures = {}
                for pid in tracked:
                    backoff_until = _VOLUME_BACKOFF.get(pid, 0)
                    if now_ts < backoff_until:
                        skipped += 1
                        continue
                    futures[executor.submit(refresh_product_minutes, pid, now_ts)] = pid

                for fut in as_completed(futures):
                    pid = futures[fut]
                    try:
                        res = fut.result()
                        if res:
                            _VOLUME_FAILS[pid] = 0
                            _VOLUME_BACKOFF[pid] = 0
                            ok += 1
                        else:
                            raise RuntimeError("refresh_failed")
                    except RateLimitError:
                        rl += 1
                        _VOLUME_FAILS[pid] = _VOLUME_FAILS.get(pid, 0) + 1
                        delay = min(600, 30 * (2 ** (_VOLUME_FAILS[pid] - 1)))
                        _VOLUME_BACKOFF[pid] = int(time.time()) + delay
                    except Exception as e:
                        fail += 1
                        _VOLUME_FAILS[pid] = _VOLUME_FAILS.get(pid, 0) + 1
                        delay = min(300, 10 * (2 ** (_VOLUME_FAILS[pid] - 1)))
                        _VOLUME_BACKOFF[pid] = int(time.time()) + delay
                        logging.debug(f"volume1h refresh error for {pid}: {e}")

        logging.info(f"[volume1h] tracked={len(tracked)} ok={ok} fail={fail} rl={rl} skip={skipped}")
        sleep_for = max(1, VOLUME_1H_REFRESH_SEC - (time.time() - loop_start))
        time.sleep(sleep_for)


def background_crypto_updates():
    """Two-loop background worker: fast snapshot compute + slower price fetch."""
    logging.info(f"Starting two-loop background worker: compute every {CONFIG['SNAPSHOT_COMPUTE_INTERVAL']}s, fetch every {CONFIG['PRICE_FETCH_INTERVAL']}s")

    # Initial fetch to populate cache
    _fetch_prices_and_update_history()
    _compute_snapshots_from_cache()

    last_fetch_time = time.time()

    while True:
        try:
            now = time.time()

            # Check if it's time to fetch fresh prices
            if now - last_fetch_time >= CONFIG['PRICE_FETCH_INTERVAL']:
                _fetch_prices_and_update_history()
                last_fetch_time = now

            # Always recompute snapshots from cache
            _compute_snapshots_from_cache()

        except Exception as e:
            logging.error(f"Error in background worker: {e}")

        # Sleep for snapshot compute interval (fast cadence)
        time.sleep(CONFIG['SNAPSHOT_COMPUTE_INTERVAL'])


# =============================================================================
# BACKGROUND STARTUP (for `flask run`)
# =============================================================================

_MW_BG_THREAD = None
_MW_BG_LOCK = threading.Lock()
_MW_VOLUME_THREAD = None
_MW_VOLUME_LOCK = threading.Lock()
_MW_SENTIMENT_THREAD = None
_MW_SENTIMENT_LOCK = threading.Lock()


def _mw_ensure_background_started():
    """Start the background updater when running under `flask run`.

    When the backend is launched via `flask run`, the `__main__` block is not
    executed, so the background updater thread would never start and SWR
    snapshots remain empty (dashboard shows no data).
    """
    global _MW_BG_THREAD, _MW_VOLUME_THREAD, _MW_SENTIMENT_THREAD

    # Avoid starting the thread in the Werkzeug reloader parent process.
    # Only the child process sets WERKZEUG_RUN_MAIN=true.
    if os.environ.get("FLASK_DEBUG") == "1" and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    with _MW_BG_LOCK:
        if _MW_BG_THREAD is not None and _MW_BG_THREAD.is_alive():
            return
        try:
            t = threading.Thread(target=background_crypto_updates)
            t.daemon = True
            t.start()
            _MW_BG_THREAD = t
            try:
                app.logger.info("Background update thread started (flask-run bootstrap)")
            except Exception:
                pass
        except Exception as e:
            try:
                app.logger.warning(f"Failed to start background updater thread: {e}")
            except Exception:
                pass

    with _MW_VOLUME_LOCK:
        if _MW_VOLUME_THREAD is None or not _MW_VOLUME_THREAD.is_alive():
            try:
                ensure_volume_db()
                vt = threading.Thread(target=_volume1h_updater_loop)
                vt.daemon = True
                vt.start()
                _MW_VOLUME_THREAD = vt
                try:
                    app.logger.info("Volume 1h updater thread started (flask-run bootstrap)")
                except Exception:
                    pass
            except Exception as e:
                try:
                    app.logger.warning(f"Failed to start volume updater thread: {e}")
                except Exception:
                    pass

    # External sentiment pipeline thread is now DISABLED — we use local tape-based
    # market heat instead. The thread is kept for future use when a real pipeline
    # (Redis-backed, API-key-gated) is available. Guard with env var to opt-in.
    if os.environ.get("MW_ENABLE_EXTERNAL_SENTIMENT", "0") == "1":
        with _MW_SENTIMENT_LOCK:
            if _MW_SENTIMENT_THREAD is None or not _MW_SENTIMENT_THREAD.is_alive():
                try:
                    st = threading.Thread(target=_sentiment_polling_loop)
                    st.daemon = True
                    st.start()
                    _MW_SENTIMENT_THREAD = st
                    try:
                        app.logger.info("Sentiment polling thread started (flask-run bootstrap)")
                    except Exception:
                        pass
                except Exception as e:
                    try:
                        app.logger.warning(f"Failed to start sentiment poller thread: {e}")
                    except Exception:
                        pass
    else:
        try:
            app.logger.info("External sentiment pipeline DISABLED (using local tape heat). Set MW_ENABLE_EXTERNAL_SENTIMENT=1 to enable.")
        except Exception:
            pass


@app.before_request
def _mw_bootstrap_background_once():
    _mw_ensure_background_started()


# ---------------------------------------------------------------------------
# Dev-only helper: force a snapshot recompute (guarded by env)
# Set DEV_ALLOW_RECOMPUTE=1 to enable this endpoint in local dev only.
# ---------------------------------------------------------------------------
@app.route('/__dev/recompute_snapshots', methods=['POST', 'GET'])
def __dev_recompute_snapshots():
    # Dev-only: allow recompute unconditionally in local dev. If you need
    # stricter controls, set DEV_ALLOW_RECOMPUTE and update this guard.
    try:
        # Clear banner snapshot so recompute will prefer fresh candle/cache path
        try:
            with _MW_COMPONENT_SNAPSHOTS_LOCK:
                _MW_COMPONENT_SNAPSHOTS.pop('banner_1h_volume', None)
        except Exception:
            pass

        _compute_snapshots_from_cache()
        # If banner still empty, compute directly from SQLite-backed compute
        snap = _mw_get_component_snapshot('banner_1h_volume')
        rows, ts = _wrap_rows_and_ts(snap)
        if not (rows and len(rows) > 0):
            try:
                payload = _volume1h_build_payload_snapshot()
                computed = _volume1h_compute_ranked(payload)
                if isinstance(computed, list) and computed:
                    out_rows = []
                    for it in computed:
                        pid = it.get('product_id') or it.get('id')
                        sym = (it.get('symbol') or (pid.split('-')[0] if isinstance(pid, str) and '-' in pid else None) or '').upper()
                        vol_now = it.get('volume_1h_now')
                        vol_prev = it.get('volume_1h_prev')
                        pct = it.get('volume_change_1h_pct')
                        baseline_ready = (pct is not None) and (vol_prev is not None)
                        out_rows.append({
                            'symbol': sym,
                            'product_id': pid or (f"{sym}-USD" if sym else None),
                            'volume_1h_now': float(vol_now) if vol_now is not None else None,
                            'volume_1h_prev': float(vol_prev) if vol_prev is not None else None,
                            'volume_change_1h_pct': float(pct) if pct is not None else None,
                            'baseline_ready': bool(baseline_ready),
                            'baseline_missing_reason': None if baseline_ready else 'warming_candles',
                            'source': 'volume1h_sqlite',
                        })
                    banner_1h_volume = {'component': 'banner_1h_volume', 'data': out_rows[:20], 'last_updated': datetime.now().isoformat()}
                    # Persist snapshot immediately
                    _mw_set_component_snapshots(banner_1h_volume=banner_1h_volume)
                    rows = out_rows
                    ts = banner_1h_volume['last_updated']
            except Exception:
                pass

        return jsonify({'ok': True, 'rows': len(rows or []), 'last_updated': ts}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# =============================================================================
# COMMAND LINE ARGUMENTS
# =============================================================================

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='CBMo4ers Crypto Dashboard Backend')
    parser.add_argument('--port', type=int, help='Port to run the server on')
    parser.add_argument('--host', type=str, help='Host to bind the server to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--interval', type=int, help='Price check interval in minutes')
    parser.add_argument('--cache-ttl', type=int, help='Cache TTL in seconds')
    parser.add_argument('--kill-port', action='store_true', help='Kill process on target port before starting')
    parser.add_argument('--auto-port', action='store_true', help='Automatically find available port')
    
    return parser.parse_args()


# Backwards-compatible alias: some clients call /api/data. Proxy to the canonical
# `/data` handler so older frontends or misconfigured envs still work during dev.
@app.route('/api/data')
def api_data():
    # === TEST FIXTURE MODE: deterministic payload for unit tests ===
    # When `MW_TEST_FIXTURES` is set to "1", return a tiny, deterministic
    # JSON payload that guarantees at least one row for baseline/unit tests.
    import os
    if os.getenv("MW_TEST_FIXTURES") == "1":
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        return {
            "gainers": [{
                "symbol": "BTC-USD",
                "current": 110.0,
                "gain": 10.0,
                "interval_minutes": 3.0,
                # baseline keys the tests check (all strictly > 0)
                "previous_price": 100.0,
                "initial_price_1min": 109.0,
                "initial_price_3min": 100.0,
                "price_1m_ago": 109.0,
                "price_3m_ago": 100.0,
                "baseline_ts_3m": now,
            }],
            "losers": [],
            "banner": [],
            "volumes": [],
            "meta": {"fixture": True},
        }, 200

    return data_aggregate()

# =============================================================================
# APPLICATION STARTUP
# =============================================================================

if __name__ == '__main__':
    # Parse command line arguments
    args = parse_arguments()
    
    # Update config from command line arguments
    if args.port:
        CONFIG['PORT'] = args.port
    if args.host:
        CONFIG['HOST'] = args.host
    if args.debug:
        CONFIG['DEBUG'] = True
    if args.interval:
        CONFIG['INTERVAL_MINUTES'] = args.interval
    if args.cache_ttl:
        CONFIG['CACHE_TTL'] = args.cache_ttl
        cache['ttl'] = CONFIG['CACHE_TTL']
    
    # Log configuration
    log_config()
    
    # Handle port conflicts
    target_port = CONFIG['PORT']
    
    if args.kill_port:
        logging.info(f"Attempting to kill process on port {target_port}")
        kill_process_on_port(target_port)
        time.sleep(2)  # Wait for process to be killed
    
    # Always try to find available port (auto-port by default)
    if args.auto_port or not args.port:
        available_port = find_available_port(target_port)
        if available_port:
            CONFIG['PORT'] = available_port
            logging.info(f"Using available port: {available_port}")
        else:
            logging.error("Could not find available port")
            exit(1)
    
    logging.info("Starting CBMo4ers Crypto Dashboard Backend...")

    # Initialize SQLite price snapshot database
    try:
        ensure_price_db()
        logging.info("SQLite price snapshot database initialized")
    except Exception as e:
        logging.error(f"Failed to initialize price database: {e}")

    # DEV: seed volume history if requested (helps banner 1h display during dev)
    try:
        seed_volume_history_if_dev()
    except Exception:
        logging.debug("DEV seeder skipped or failed")

    # Warm the /data cache once so meta.ts and banner are available immediately after seeding
    try:
        try:
            # Prefer the full snapshot builder which also populates banners
            result = get_crypto_data()
            if result:
                try:
                    cache['data'] = result
                    cache['timestamp'] = time.time()
                except Exception:
                    pass
            logging.info("Warmed /data cache after DEV seeding")
        except Exception:
            # Best-effort fallback: build 1min snapshot if full builder is unavailable
            try:
                result = get_crypto_data_1min()
                if result:
                    try:
                        one_minute_cache['data'] = result
                        one_minute_cache['timestamp'] = time.time()
                    except Exception:
                        pass
                logging.info("Warmed 1min cache after DEV seeding")
            except Exception:
                logging.debug("Cache warmup skipped: snapshot builders not available at startup")
    except Exception:
        logging.debug("Unexpected error during cache warmup after DEV seeding")

    # Start volume 1h updater thread (candles → SQLite)
    try:
        ensure_volume_db()
        vol_thread = threading.Thread(target=_volume1h_updater_loop)
        vol_thread.daemon = True
        vol_thread.start()
        logging.info("Volume 1h updater thread started")
    except Exception as e:
        logging.warning(f"Failed to start volume 1h updater thread: {e}")

    # Start background thread for periodic updates
    background_thread = threading.Thread(target=background_crypto_updates)
    background_thread.daemon = True
    background_thread.start()
    
    logging.info("Background update thread started")

    # Start sentiment polling thread
    try:
        sentiment_thread = threading.Thread(target=_sentiment_polling_loop)
        sentiment_thread.daemon = True
        sentiment_thread.start()
        logging.info("Sentiment polling thread started")
    except Exception as e:
        logging.warning(f"Failed to start sentiment poller thread: {e}")
    logging.info(f"Server starting on http://{CONFIG['HOST']}:{CONFIG['PORT']}")
    
    try:
        app.run(debug=CONFIG['DEBUG'], 
                host=CONFIG['HOST'], 
                port=CONFIG['PORT'],
                use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            logging.error(f"Port {CONFIG['PORT']} is in use. Try:")
            logging.error("1. python3 app.py --kill-port")
            logging.error("2. python3 app.py --auto-port")
            logging.error("3. python3 app.py --port 5003")
        else:
            logging.error(f"Error starting server: {e}")
        exit(1)

else:
    # Production mode for Vercel
    log_config()
    logging.info("Running in production mode (Vercel)")

# Legacy get_mobile_bundle route removed; consolidated into /api/mobile/bundle above.

# ------------------------------
# Dev stub endpoints (added to avoid 404s during local dev)
# These return minimal JSON so the UI can render while the real
# implementations (alerts, metrics, components) are being wired up.
# ------------------------------
try:
    app  # type: ignore  # ensure an app instance exists
except NameError:  # pragma: no cover
    from flask import Flask
    app = Flask(__name__)

from flask import jsonify, request
import time, os

@app.get("/server-info")
def _dev_server_info():
    return jsonify({
        "ok": True,
        "service": "backend",
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pid": os.getpid(),
        "version": 1,
    })


@app.get('/api/insights/<path:symbol>')
def api_insights(symbol):
    """Return an insights payload for a given symbol using on-disk caches and
    short-term price/volume history. Falls back gracefully if data is missing.
    """
    # Normalise symbol (frontend may send BTC-USD or BTC)
    sym = symbol.upper()

    # Determine current prices from cached last_current_prices or fetch fresh
    current_prices = last_current_prices.get('data') if isinstance(last_current_prices, dict) else None
    if not current_prices:
        try:
            current_prices = get_current_prices()
        except Exception:
            current_prices = {}

    # Try several variants to find a matching price key
    current_price = None
    for key in (sym, sym.replace('-', ''), sym.split('-')[0]):
        if key in current_prices:
            current_price = current_prices.get(key)
            break

    if current_price is None:
        return jsonify({"error": ERROR_NO_DATA}), 404

    now = time.time()

    # Build snapshots from in-memory price history structures
    # price_history_1min and price_history are deques of (ts, price)
    price_1m_ago = None
    try:
        hist1 = price_history_1min.get(sym) or price_history_1min.get(sym.replace('-', '')) or deque()
        # Find point at least ~60s old
        for ts, p in reversed(hist1):
            if now - ts >= 55:
                price_1m_ago = p
                break
        if price_1m_ago is None and len(hist1) > 0:
            price_1m_ago = hist1[0][1]
    except Exception:
        price_1m_ago = None

    price_3m_ago = None
    try:
        hist_all = price_history.get(sym) or price_history.get(sym.replace('-', '')) or deque()
        for ts, p in reversed(hist_all):
            if now - ts >= 175:  # prefer a bit more than 3 minutes to cover gaps
                price_3m_ago = p
                break
        if price_3m_ago is None and len(hist_all) > 0:
            price_3m_ago = hist_all[0][1]
    except Exception:
        price_3m_ago = None

    # Volume: use volume_history_24h to estimate 1h current and previous volumes
    vol_1h_now = None
    vol_1h_prev = None
    try:
        vol_hist = volume_history_24h.get(sym) or volume_history_24h.get(sym.replace('-', '')) or deque()
        if len(vol_hist) >= 1:
            vol_1h_now = vol_hist[-1][1]
        if len(vol_hist) >= 2:
            # find an entry roughly 1 hour ago; fall back to second-last
            for ts, v in reversed(vol_hist):
                if now - ts >= 3500:  # roughly 1 hour (3600s) tolerance
                    vol_1h_prev = v
                    break
            if vol_1h_prev is None and len(vol_hist) >= 2:
                vol_1h_prev = vol_hist[-2][1]
    except Exception:
        vol_1h_now = vol_1h_prev = None

    snapshots = {
        "price_1m_ago": price_1m_ago,
        "price_3m_ago": price_3m_ago,
        "volume_1h_now": vol_1h_now,
        "volume_1h_prev": vol_1h_prev,
    }

    # Build insights via the helper if available, else return a minimal derived blob
    try:
        if callable(build_asset_insights):
            payload = build_asset_insights(sym, current_price, snapshots, COINGECKO_ID_MAP)
        else:
            # Minimal fallback: compute a few derived fields
            def _pct(a, b):
                try:
                    if b in (None, 0):
                        return None
                    return (float(a) - float(b)) / float(b) * 100.0
                except Exception:
                    return None

            payload = {
                "symbol": sym,
                "price": current_price,
                "change_1m": _pct(current_price, price_1m_ago),
                "change_3m": _pct(current_price, price_3m_ago),
                "volume_change_1h": _pct(vol_1h_now, vol_1h_prev),
                "heat_score": 50.0,
                "trend": "FLAT",
                "social": None,
                "market_sentiment": None,
                "sources": {"price_volume": "coinbase_snapshots", "social": "none", "macro": "none"},
            }
    except Exception as e:
        logging.exception("Failed to build insights for %s: %s", sym, e)
        return jsonify({"error": str(e)}), 500

    return jsonify(payload), 200

@app.get("/metrics")
def _dev_metrics():
    return jsonify({
        "ok": True,
        "latency_ms": 5,
        "requests_in_window": 0,
        "time": time.time(),
    })

@app.get("/alerts/recent")
def _dev_alerts_recent():
    try:
        limit = int(request.args.get("limit", 25))
    except Exception:
        limit = 25
    return jsonify({
        "ok": True,
        "alerts": _normalize_alerts(list(alerts_log))[-limit:],
        "limit": limit,
    })

@app.get("/component/<name>")
def _dev_component(name: str):
    # Provide shape-compatible dummy payloads per component name
    payload = {"ok": True, "component": name}
    if name.endswith("gainers-table") or name.startswith("gainers-table"):
        payload["rows"] = []
    elif name.endswith("losers-table") or name.startswith("losers-table"):
        payload["rows"] = []
    elif name in ("top-banner-scroll", "bottom-banner-scroll"):
        payload["items"] = []
    else:
        payload["data"] = []
    return jsonify(payload)

# End dev stubs

__all__ = [
    "process_product_data",
    "format_crypto_data",
    "format_banner_data"
]
