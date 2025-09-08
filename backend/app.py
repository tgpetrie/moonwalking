import os
import argparse
import socket
import subprocess
import sys
import math
from flask import Flask, jsonify, request, g
from flask_talisman import Talisman
from flask_cors import CORS
import requests
import time
import threading
from collections import defaultdict, deque
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from datetime import datetime, timedelta

from watchlist import watchlist_bp, watchlist_db
from reliability import stale_while_revalidate
from metrics import collect_swr_cache_stats, emit_prometheus, emit_swr_prometheus
from alerting import AlertNotifier
try:
    # optional insight memory (may not exist early in startup)
    from watchlist import _insights_memory as INSIGHTS_MEMORY
except Exception:
    INSIGHTS_MEMORY = None

from logging_config import setup_logging as _setup_logging, log_config as _log_config_with_param
from logging_config import REQUEST_ID_CTX
import uuid
from pyd_schemas import HealthResponse, MetricsResponse, Gainers1mComponent
from social_sentiment import get_social_sentiment
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

# Define missing constants
ERROR_NO_DATA = "No data available"

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

app = Flask(__name__)
Talisman(app, content_security_policy={
    'default-src': ["'self'"],
    'img-src': ["'self'", 'data:'],
    'script-src': ["'self'"],
    'style-src': ["'self'"],
    # Add other directives as needed
},
strict_transport_security=True,
frame_options='deny',
x_xss_protection=True,
x_content_type_options=True)

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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'crypto-dashboard-secret')

# Add startup time tracking
startup_time = time.time()

# Configure allowed CORS origins from environment
cors_env = os.environ.get('CORS_ALLOWED_ORIGINS', '*')
if cors_env == '*':
    cors_origins = '*'
else:
    cors_origins = [origin.strip() for origin in cors_env.split(',') if origin.strip()]

CORS(app, origins=cors_origins)

# Register blueprints after final app creation
app.register_blueprint(watchlist_bp)

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
    if not data:
        return None
    gainers = data.get('gainers', [])
    gainers_table_data = []
    for i, coin in enumerate(gainers[:20]):
        gainers_table_data.append({
            'rank': i + 1,
            'symbol': coin['symbol'],
            'current_price': coin['current'],
            'price_change_percentage_1min': coin['gain'],
            'initial_price_1min': coin['initial_1min'],
            'actual_interval_minutes': coin.get('interval_minutes', 1),
            'peak_gain': coin.get('peak_gain', coin['gain']),
            'trend_direction': coin.get('trend_direction', 'flat'),
            'trend_streak': coin.get('trend_streak', 0),
            'trend_score': coin.get('trend_score', 0.0),
            'trend_delta': coin.get('trend_delta', 0.0),
            'momentum': 'strong' if coin['gain'] > 5 else 'moderate',
            'alert_level': 'high' if coin['gain'] > 10 else 'normal'
        })
    return {
        'component': 'gainers_table_1min',
        'data': gainers_table_data,
        'count': len(gainers_table_data),
        'table_type': 'gainers',
        'time_frame': '1_minute',
        'update_interval': 10000,
        'last_updated': datetime.now().isoformat()
    }

@stale_while_revalidate(ttl=_GAINERS_3M_SWR_TTL, stale_window=_GAINERS_3M_SWR_STALE)
@ttl_cache(ttl=int(_GAINERS_3M_SWR_TTL))
def _get_gainers_table_3min_swr():
    data = get_crypto_data()
    if not data:
        return None
    gainers = data.get('gainers', [])
    gainers_table_data = []
    for i, coin in enumerate(gainers[:20]):
        sym = coin['symbol']
        direction, streak, score = _update_3m_trend(sym, coin.get('gain', 0))
        gainers_table_data.append({
            'rank': i + 1,
            'symbol': coin['symbol'],
            'current_price': coin['current'],
            'price_change_percentage_3min': coin['gain'],
            'initial_price_3min': coin['initial_3min'],
            'actual_interval_minutes': coin.get('interval_minutes', 3),
            'trend_direction': direction,
            'trend_streak': streak,
            'trend_score': score,
            'momentum': 'strong' if coin['gain'] > 5 else 'moderate',
            'alert_level': 'high' if coin['gain'] > 10 else 'normal'
        })
    return {
        'component': 'gainers_table',
        'data': gainers_table_data,
        'count': len(gainers_table_data),
        'table_type': 'gainers',
        'time_frame': '3_minutes',
        'update_interval': 3000,
        'last_updated': datetime.now().isoformat()
    }

@stale_while_revalidate(ttl=_LOSERS_3M_SWR_TTL, stale_window=_LOSERS_3M_SWR_STALE)
@ttl_cache(ttl=int(_LOSERS_3M_SWR_TTL))
def _get_losers_table_3min_swr():
    data = get_crypto_data()
    if not data:
        return None
    losers = data.get('losers', [])
    losers_table_data = []
    for i, coin in enumerate(losers[:20]):
        sym = coin['symbol']
        direction, streak, score = _update_3m_trend(sym, coin.get('gain', 0))
        losers_table_data.append({
            'rank': i + 1,
            'symbol': coin['symbol'],
            'current_price': coin['current'],
            'price_change_percentage_3min': coin['gain'],
            'initial_price_3min': coin['initial_3min'],
            'actual_interval_minutes': coin.get('interval_minutes', 3),
            'trend_direction': direction,
            'trend_streak': streak,
            'trend_score': score,
            'momentum': 'strong' if coin['gain'] < -5 else 'moderate',
            'alert_level': 'high' if coin['gain'] < -10 else 'normal'
        })
    return {
        'component': 'losers_table',
        'data': losers_table_data,
        'count': len(losers_table_data),
        'table_type': 'losers',
        'time_frame': '3_minutes',
        'update_interval': 3000,
        'last_updated': datetime.now().isoformat()
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
        return jsonify([])
    syms = [s.strip().upper() for s in syms_param.split(',') if s.strip()]
    out = []
    now_ms = int(time.time() * 1000)
    for sym in syms:
        try:
            s = get_social_sentiment(sym)
            dist = s.get('sentiment_distribution') or {}
            metrics = s.get('social_metrics') or {}
            tw = (metrics.get('twitter') or {}).get('mentions_24h') or 0
            rd = (metrics.get('reddit') or {}).get('posts_24h') or 0
            tg = (metrics.get('telegram') or {}).get('messages_24h') or 0
            total_mentions = int(tw) + int(rd) + int(tg)
            out.append({
                'symbol': sym,
                'ts': now_ms,
                'mentions': total_mentions,
                'sent_score': float((s.get('overall_sentiment') or {}).get('score') or 0.0),
                'pos': float(dist.get('positive') or 0.0),
                'neg': float(dist.get('negative') or 0.0),
                'velocity': 0.0,
                'source_mix': {
                    'twitter': int(tw),
                    'reddit': int(rd),
                    'telegram': int(tg),
                },
            })
        except Exception:
            continue
    return jsonify(out)

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
    'MAX_PRICE_HISTORY': int(os.environ.get('MAX_PRICE_HISTORY', 20)),  # Keep last 20 data points
    'PORT': int(os.environ.get('PORT', 5001)),  # Default port
    'HOST': os.environ.get('HOST', '0.0.0.0'),  # Default host
    'DEBUG': os.environ.get('DEBUG', 'False').lower() == 'true',  # Debug mode
    'UPDATE_INTERVAL': int(os.environ.get('UPDATE_INTERVAL', 60)),  # Background update interval in seconds
    'MAX_COINS_PER_CATEGORY': int(os.environ.get('MAX_COINS_PER_CATEGORY', 15)),  # Max coins to return
    'MIN_VOLUME_THRESHOLD': int(os.environ.get('MIN_VOLUME_THRESHOLD', 1000000)),  # Minimum volume for banner
    'MIN_CHANGE_THRESHOLD': float(os.environ.get('MIN_CHANGE_THRESHOLD', 1.0)),  # Minimum % change for banner
    'API_TIMEOUT': int(os.environ.get('API_TIMEOUT', 10)),  # API request timeout
    'CHART_DAYS_LIMIT': int(os.environ.get('CHART_DAYS_LIMIT', 30)),  # Max days for chart data
    # 1-minute feature load controls
    'ENABLE_1MIN': os.environ.get('ENABLE_1MIN', 'true').lower() == 'true',  # Master switch
    'ONE_MIN_REFRESH_SECONDS': int(os.environ.get('ONE_MIN_REFRESH_SECONDS', 45)),  # Throttle 1-min recompute (default 45s)
    # 1-minute retention / hysteresis controls
    'ONE_MIN_ENTER_PCT': float(os.environ.get('ONE_MIN_ENTER_PCT', 0.15)),   # % change to ENTER list
    'ONE_MIN_STAY_PCT': float(os.environ.get('ONE_MIN_STAY_PCT', 0.05)),     # lower % to remain after entering
    'ONE_MIN_MAX_COINS': int(os.environ.get('ONE_MIN_MAX_COINS', 25)),       # cap displayed coins
    'ONE_MIN_DWELL_SECONDS': int(os.environ.get('ONE_MIN_DWELL_SECONDS', 90)), # minimum time to stay once entered
    # Alert hygiene (streak-triggered alerts with cooldown)
    'ALERTS_COOLDOWN_SECONDS': int(os.environ.get('ALERTS_COOLDOWN_SECONDS', 300)),  # 5 minutes
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
price_history = defaultdict(lambda: deque(maxlen=CONFIG['MAX_PRICE_HISTORY']))
price_history_1min = defaultdict(lambda: deque(maxlen=CONFIG['MAX_PRICE_HISTORY'])) # For 1-minute changes
# Cache / state for 1-min data to prevent hammering APIs
one_minute_cache = {"data": None, "timestamp": 0}
last_current_prices = {"data": None, "timestamp": 0}
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
# New trend caches for other intervals/metrics
three_minute_trends = {}
one_hour_price_trends = {}
one_hour_volume_trends = {}
# Track 24h volume snapshots to estimate 1h volume deltas: symbol -> deque[(ts, vol_24h)]
volume_history_24h = defaultdict(lambda: deque(maxlen=180))

# -----------------------------------------------------------------------------
# Trend Alert Hygiene: fire on streak thresholds with cooldown per scope/symbol
# -----------------------------------------------------------------------------
alerts_state = {
    '1m': {},
    '3m': {},
    '1h_price': {},
    '1h_volume': {},
}
alerts_log = deque(maxlen=200)

def _maybe_fire_trend_alert(scope: str, symbol: str, direction: str, streak: int, score: float) -> None:
    """Fire an alert when a trend streak crosses configured thresholds with cooldown."""
    try:
        thresholds = CONFIG.get('ALERTS_STREAK_THRESHOLDS', [3, 5])
        if direction == 'flat' or not thresholds:
            return
        # Highest threshold reached (if any)
        reached = max([t for t in thresholds if isinstance(t, int) and streak >= t], default=None)
        if reached is None:
            return
        now = time.time()
        last = alerts_state.get(scope, {}).get(symbol, 0)
        if now - last >= CONFIG.get('ALERTS_COOLDOWN_SECONDS', 300):
            msg = f"{scope} trend {direction} x{streak} on {symbol} (>= {reached}; score {float(score or 0.0):.2f})"
            alerts_log.append({
                'ts': datetime.now().isoformat(),
                'scope': scope,
                'symbol': symbol,
                'direction': direction,
                'streak': int(streak),
                'score': round(float(score or 0.0), 3),
                'message': msg
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
    global CONFIG
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
    'MAX_COINS_PER_CATEGORY': {'type': int, 'min': 1, 'max': 500},
    'MIN_VOLUME_THRESHOLD': {'type': int, 'min': 0, 'max': 10_000_000_000},
    'MIN_CHANGE_THRESHOLD': {'type': float, 'min': 0.0, 'max': 1000.0},
    'API_TIMEOUT': {'type': int, 'min': 1, 'max': 60},
    'CHART_DAYS_LIMIT': {'type': int, 'min': 1, 'max': 365},
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
        return jsonify({'config': _serialize_config(CONFIG), 'limits': _serialize_limits(VALIDATABLE_CONFIG)})
    data = request.get_json(silent=True) or {}
    to_apply, errors = validate_config_patch(data)
    status = 200 if not errors else 400 if not to_apply else 207
    if to_apply:
        update_config(to_apply)
    return jsonify({'applied': to_apply, 'errors': errors, 'config': CONFIG}), status

# =============================================================================
# EXISTING FUNCTIONS (Updated with dynamic config)
# =============================================================================

def get_coinbase_prices():
    """Fetch current prices from Coinbase (optimized for speed)"""
    try:
        products_response = requests.get(COINBASE_PRODUCTS_URL, timeout=CONFIG['API_TIMEOUT'])
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
            
            # Reorder products to prioritize major coins
            prioritized_products = []
            remaining_products = []
            
            for product in usd_products:
                if product["id"] in major_coins:
                    prioritized_products.append(product)
                else:
                    remaining_products.append(product)
            
            # Combine prioritized + remaining, but limit total to 100 for speed
            all_products = prioritized_products + remaining_products[:100-len(prioritized_products)]
            
            # Use ThreadPoolExecutor for concurrent API calls
            def fetch_ticker(product):
                """Fetch ticker data for a single product (robust to missing/None price).

                Returns (symbol, price) on success, ('__RL__', None) on 429 rate-limit,
                or (None, None) for other failures.
                """
                symbol = product["id"]
                ticker_url = f"https://api.exchange.coinbase.com/products/{symbol}/ticker"
                try:
                    ticker_response = requests.get(ticker_url, timeout=1.5)
                    if ticker_response.status_code == 200:
                        try:
                            ticker_data = ticker_response.json()
                        except ValueError:
                            logging.debug(f"ticker {symbol} returned invalid json")
                            return None, None
                        price_val = ticker_data.get('price')
                        if price_val is None:
                            logging.debug(f"ticker {symbol} missing price field")
                            return None, None
                        try:
                            price = float(price_val)
                        except (TypeError, ValueError):
                            logging.debug(f"ticker {symbol} price parse fail: {price_val}")
                            return None, None
                        if price > 0:
                            return symbol, price
                    elif ticker_response.status_code == 429:
                        # propagate a rate-limit marker so caller can escalate backoff
                        logging.debug(f"ticker {symbol} rate limited (429)")
                        return '__RL__', None
                    else:
                        logging.debug(f"ticker {symbol} status {ticker_response.status_code}")
                except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout) as e:
                    logging.debug(f"ticker {symbol} timeout {e}")
                except requests.exceptions.RequestException as e:
                    logging.debug(f"ticker {symbol} request err {e}")
                except Exception as ticker_error:
                    logging.debug(f"Failed to get ticker for {symbol}: {ticker_error}")
                return None, None

            # Use ThreadPoolExecutor for faster concurrent API calls
            with ThreadPoolExecutor(max_workers=10) as executor:
                # Submit all tasks
                future_to_product = {executor.submit(fetch_ticker, product): product 
                                   for product in all_products[:50]}
                
                # Collect results as they complete
                for future in as_completed(future_to_product):
                    symbol, price = future.result()
                    if symbol and price:
                        current_prices[symbol] = price
            
            logging.info(f"Successfully fetched {len(current_prices)} prices from Coinbase")
            return current_prices
        else:
            logging.error(f"Coinbase products API Error: {products_response.status_code}")
            return {}
    except Exception as e:
        logging.error(f"Error fetching current prices from Coinbase: {e}")
        return {}

def calculate_interval_changes(current_prices):
    """Calculate price changes over configured interval (default 3 minutes) using interpolation for accuracy."""
    current_time = time.time()
    interval_seconds = CONFIG['INTERVAL_MINUTES'] * 60

    # Update price history with current prices
    for symbol, price in current_prices.items():
        if price > 0:
            price_history[symbol].append((current_time, price))

    formatted_data = []
    target_ts_offset = interval_seconds

    for symbol, price in current_prices.items():
        if price <= 0:
            continue

        history = price_history[symbol]
        if len(history) < 2:
            continue

        # Ensure chronological list
        hist_list = list(history)
        target_ts = current_time - target_ts_offset

        interval_price = None
        interval_time = None

        # Case A: All points newer than target -> use oldest available (short interval)
        if hist_list[0][0] > target_ts:
            interval_time, interval_price = hist_list[0]
        # Case B: All points older than target -> use latest older (long interval)
        elif hist_list[-1][0] <= target_ts:
            interval_time, interval_price = hist_list[-1]
        else:
            # Case C: Interpolate between the two bracketing points around target_ts
            left = None
            right = None
            for i in range(len(hist_list) - 1):
                t0, p0 = hist_list[i]
                t1, p1 = hist_list[i + 1]
                if t0 <= target_ts <= t1:
                    left = (t0, p0)
                    right = (t1, p1)
                    break
            if left and right and right[0] > left[0] and all(x is not None for x in (left[1], right[1])):
                t0, p0 = left
                t1, p1 = right
                # Linear interpolation
                ratio = (target_ts - t0) / (t1 - t0)
                interval_price = p0 + (p1 - p0) * ratio
                interval_time = target_ts
            else:
                # Fallback to latest older point if interpolation failed
                # Find latest point <= target_ts
                for t, p in reversed(hist_list):
                    if t <= target_ts:
                        interval_time, interval_price = t, p
                        break
                # If still none, use oldest
                if interval_price is None:
                    interval_time, interval_price = hist_list[0]

        if interval_price is None or interval_price <= 0:
            continue

        price_change = ((price - interval_price) / interval_price) * 100
        actual_interval_minutes = (
            CONFIG['INTERVAL_MINUTES'] if interval_time == target_ts else (current_time - interval_time) / 60
        )

        if abs(price_change) >= 0.01:
            formatted_data.append({
                "symbol": symbol,
                "current_price": price,
                "initial_price_3min": interval_price,
                "price_change_percentage_3min": price_change,
                "actual_interval_minutes": actual_interval_minutes
            })

    return formatted_data

def calculate_1min_changes(current_prices):
    """Calculate price changes over 1 minute"""
    current_time = time.time()
    interval_seconds = 60 # 1 minute
    
    # Update price history with current prices
    for symbol, price in current_prices.items():
        if price > 0:
            price_history_1min[symbol].append((current_time, price))
    
    # Calculate changes for each symbol
    formatted_data = []
    for symbol, price in current_prices.items():
        if price <= 0:
            continue
            
        history = price_history_1min[symbol]
        if len(history) < 2:
            continue
            
        # Find price from interval ago (or earliest available)
        interval_price = None
        interval_time = None
        
        for timestamp, historical_price in history:
            if current_time - timestamp >= interval_seconds:
                interval_price = historical_price
                interval_time = timestamp
                break
        
        # If no interval data, use oldest available
        if interval_price is None and len(history) >= 2:
            interval_price = history[0][1]
            interval_time = history[0][0]
        
        if interval_price is None or interval_price <= 0:
            continue
            
        # Calculate percentage change
        price_change = ((price - interval_price) / interval_price) * 100
        actual_interval_minutes = (current_time - interval_time) / 60 if interval_time else 0
        
        # Only include significant changes (configurable threshold)
        if abs(price_change) >= 0.01: # Reverted to original threshold
            formatted_data.append({
                "symbol": symbol,
                "current_price": price,
                "initial_price_1min": interval_price,
                "price_change_percentage_1min": price_change,
                "actual_interval_minutes": actual_interval_minutes
            })
    
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
                    price_change_24h = ((current_price - open_24h) / open_24h) * 100
                    
                    # Estimate 1h change
                    price_1h_estimate = current_price - ((current_price - open_24h) * 0.04)
                    price_change_1h = ((current_price - price_1h_estimate) / price_1h_estimate) * 100 if price_1h_estimate > 0 else 0
                    
                    # Only include significant moves
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
            future_to_product = {executor.submit(fetch_product_data, product): product 
                               for product in usd_products[:30]}  # Reduced to 30 for faster response
            
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
            "gain": coin["price_change_percentage_3min"],
            "interval_minutes": round(coin["actual_interval_minutes"], 1)
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

def get_crypto_data():
    """Main function to fetch and process crypto data"""
    current_time = time.time()
    
    # Check cache first
    if cache["data"] and (current_time - cache["timestamp"]) < cache["ttl"]:
        return cache["data"]
    
    try:
        # Get current prices for 3-minute calculations
        current_prices = get_current_prices()
        if not current_prices:
            logging.warning("No current prices available")
            return None
            
        # Calculate 3-minute interval changes (unique feature)
        crypto_data = calculate_interval_changes(current_prices)
        
        if not crypto_data:
            logging.warning(f"No crypto data available - {len(current_prices)} current prices, {len(price_history)} symbols with history")
            return None
        
        # Separate gainers and losers based on 3-minute changes
        gainers = [coin for coin in crypto_data if coin.get("price_change_percentage_3min", 0) > 0]
        losers = [coin for coin in crypto_data if coin.get("price_change_percentage_3min", 0) < 0]
        
        # Sort by 3-minute percentage change
        gainers.sort(key=lambda x: x["price_change_percentage_3min"], reverse=True)
        losers.sort(key=lambda x: x["price_change_percentage_3min"])
        
        # Get top movers (mix of gainers and losers)
        top_gainers = gainers[:8]
        top_losers = losers[:8]
        top24h = (top_gainers + top_losers)[:15]
        
        # Get 24h top movers for banner
        banner_24h_movers = get_24h_top_movers()
        
        result = {
            "gainers": format_crypto_data(gainers[:15]),
            "losers": format_crypto_data(losers[:15]),
            "top24h": format_crypto_data(top24h),
            "banner": format_banner_data(banner_24h_movers[:20])
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
    """Top banner: Current price + 1h % change (unique endpoint)"""
    try:
        # Get specific data for top banner - focus on price and 1h changes
        banner_data = get_24h_top_movers()
        
        if not banner_data:
            return jsonify({"error": "No banner data available"}), 503
            
        # Format specifically for top banner - normalized shape expected by clients/tests
        items = []
        for coin in banner_data[:20]:  # Top 20 for scrolling
            items.append({
                "symbol": coin["symbol"],
                "current_price": coin.get("current_price") or coin.get('current') or 0,
                "price_change_1h": coin.get("price_change_1h", 0),
                "market_cap": coin.get("market_cap", 0)
            })

        # Provide test-friendly root keys: items, count, limit, age_seconds, stale, ts
        return jsonify({
            "items": items,
            "count": len(items),
            "limit": 20,
            "age_seconds": 0,
            "stale": False,
            "ts": int(time.time())
        })
    except Exception as e:
        logging.error(f"Error in top banner endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/banner-bottom')
def get_bottom_banner():
    """Bottom banner: Volume + 1h % change (unique endpoint)"""
    try:
        # Get specific data for bottom banner - focus on volume and 1h changes
        banner_data = get_24h_top_movers()
        
        if not banner_data:
            return jsonify({"error": "No banner data available"}), 503
            
        # Sort by volume for bottom banner
        volume_sorted = sorted(banner_data, key=lambda x: x.get("volume_24h", 0), reverse=True)
        
        # Format specifically for bottom banner - normalized shape expected by clients/tests
        items = []
        for coin in volume_sorted[:20]:  # Top 20 by volume
            items.append({
                "symbol": coin["symbol"],
                "volume_24h": coin.get("volume_24h", 0),
                "price_change_1h": coin.get("price_change_1h", 0),
                "current_price": coin.get("current_price") or coin.get('current') or 0
            })

        return jsonify({
            "items": items,
            "count": len(items),
            "limit": 20,
            "age_seconds": 0,
            "stale": False,
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
    for coin in rows[:20]:
        try:
            out.append({
                "symbol": coin.get("symbol"),
                "current_price": float(coin.get("current_price", 0) or 0),
                "initial_price_1h": float(coin.get("initial_price_1h", 0) or 0),
                "price_change_1h": float(coin.get("price_change_1h", 0) or 0),
                "market_cap": float(coin.get("market_cap", 0) or 0),
            })
        except Exception:
            continue
    return out

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
                        if vol_then > 0:
                            vol_change_1h_pct = (vol_change_1h / vol_then) * 100.0
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
# Alerts API: expose recent trend alerts with cooldown-based hygiene
# -----------------------------------------------------------------------------
@app.route('/api/alerts/recent')
def get_recent_alerts():
    try:
        limit = int(request.args.get('limit', 50))
        if limit <= 0:
            limit = 50
        items = list(alerts_log)[-limit:]
        return jsonify({
            'count': len(items),
            'limit': limit,
            'alerts': items
        })
    except Exception as e:
        logging.error(f"Error in recent alerts endpoint: {e}")
        return jsonify({'error': str(e)}), 500

# =============================================================================
# EXISTING ENDPOINTS (Updated root to show new individual endpoints)

def get_crypto_data_1min():
    """Main function to fetch and process 1-minute crypto data"""
    if not CONFIG.get('ENABLE_1MIN', True):
        return None
    current_time = time.time()
    # Throttle heavy recomputation; allow front-end fetch to reuse last processed snapshot
    refresh_window = CONFIG.get('ONE_MIN_REFRESH_SECONDS', 30)
    if one_minute_cache['data'] and (current_time - one_minute_cache['timestamp']) < refresh_window:
        return one_minute_cache['data']
    try:
        # Reuse prices from background thread if fetched recently (<10s) to avoid parallel bursts
        prices_age_limit = 10
        if last_current_prices['data'] and (current_time - last_current_prices['timestamp']) < prices_age_limit:
            current_prices = last_current_prices['data']
        else:
            current_prices = get_current_prices()
            if current_prices:
                last_current_prices['data'] = current_prices
                last_current_prices['timestamp'] = current_time
        if not current_prices:
            logging.warning("No current prices available for 1-min data")
            return None

        crypto_data = calculate_1min_changes(current_prices)
        if not crypto_data:
            # On cold start we may have <2 samples per symbol; return an empty, cacheable payload instead of None (prevents 503s)
            logging.warning(f"No 1-min crypto data available after calculation - {len(current_prices)} current prices, {len(price_history_1min)} symbols with history")
            empty_result = {
                "gainers": [],
                "losers": [],
                "throttled": True,
                "refresh_seconds": CONFIG.get('ONE_MIN_REFRESH_SECONDS', 30),
                "enter_threshold_pct": CONFIG.get('ONE_MIN_ENTER_PCT', 0.15),
                "stay_threshold_pct": CONFIG.get('ONE_MIN_STAY_PCT', 0.05),
                "dwell_seconds": CONFIG.get('ONE_MIN_DWELL_SECONDS', 90),
                "retained": 0
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
        retained_coins = [data_by_symbol[s] for s in retained_symbols if s in data_by_symbol]
        gainers = [c for c in retained_coins if c.get('price_change_percentage_1min_peak', c.get('price_change_percentage_1min', 0)) > 0]
        losers = [c for c in retained_coins if c.get('price_change_percentage_1min_peak', c.get('price_change_percentage_1min', 0)) < 0]
        gainers.sort(key=lambda x: x.get('price_change_percentage_1min_peak', x.get('price_change_percentage_1min', 0)), reverse=True)
        losers.sort(key=lambda x: x.get('price_change_percentage_1min_peak', x.get('price_change_percentage_1min', 0)))

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
            seed_count = int(CONFIG.get('ONE_MIN_SEED_COUNT', 6))
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
        data = _get_gainers_table_1min_swr()
        if not data:
            return jsonify({"error": "No 1-minute data available"}), 503
        swr_meta = {
            'ttl': _GAINERS_1M_SWR_TTL,
            'stale_window': _GAINERS_1M_SWR_STALE,
            'served_cached': getattr(_get_gainers_table_1min_swr, '_swr_last_served_cached', False),
        }
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
def get_social_sentiment_endpoint(symbol):
    """Get social sentiment analysis for a specific cryptocurrency"""
    try:
        from social_sentiment import get_social_sentiment
        
        # Validate symbol format
        symbol = symbol.upper().replace('-USD', '')
        if not symbol.isalpha() or len(symbol) < 2 or len(symbol) > 10:
            return jsonify({"error": "Invalid symbol format"}), 400
        
        # Get social sentiment analysis
        sentiment_data = get_social_sentiment(symbol)
        
        return jsonify({
            "success": True,
            "data": sentiment_data,
            "timestamp": datetime.now().isoformat()
        })
        
    except ImportError as e:
        logging.error(f"Social sentiment module not available: {e}")
        return jsonify({"error": "Social sentiment analysis not available"}), 503
    except Exception as e:
        logging.error(f"Error getting social sentiment for {symbol}: {e}")
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


def background_crypto_updates():
    """Background thread to update cache periodically"""
    while True:
        try:
            # Update 3-min data cache
            data_3min = get_crypto_data()
            if data_3min:
                logging.info(f"3-min cache updated: {len(data_3min['gainers'])} gainers, {len(data_3min['losers'])} losers, {len(data_3min['banner'])} banner items")

            # Respect config before doing 1-min related processing
            if CONFIG.get('ENABLE_1MIN', True):
                current_prices = get_current_prices()
                if current_prices:
                    # Store for reuse by on-demand endpoint
                    last_current_prices['data'] = current_prices
                    last_current_prices['timestamp'] = time.time()
                    calculate_1min_changes(current_prices)
                    logging.debug(f"1-min price history updated with {len(current_prices)} new prices.")
                    _auto_log_watchlist_moves(current_prices, data_3min.get('banner') if data_3min else [])

        except Exception as e:
            logging.error(f"Error in background update: {e}")
        
        time.sleep(CONFIG['UPDATE_INTERVAL'])  # Dynamic interval

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
    
    # Start background thread for periodic updates
    background_thread = threading.Thread(target=background_crypto_updates)
    background_thread.daemon = True
    background_thread.start()
    
    logging.info("Background update thread started")
    logging.info(f"Server starting on http://{CONFIG['HOST']}:{CONFIG['PORT']}")
    
    try:
        app.run(debug=CONFIG['DEBUG'], 
                host=CONFIG['HOST'], 
                port=CONFIG['PORT'])
    except OSError as e:
        if "Address already in use" in str(e):
            logging.error(f"Port {CONFIG['PORT']} is in use. Try:")
            logging.error("1. python3 app.py --kill-port")
            logging.error("2. python3 app.py --auto-port")
            logging.error("3. python3 app.py --port 5002")
        else:
            logging.error(f"Error starting server: {e}")
        exit(1)

else:
    # Production mode for Vercel
    log_config()
    logging.info("Running in production mode (Vercel)")

# Legacy get_mobile_bundle route removed; consolidated into /api/mobile/bundle above.

__all__ = [
    "process_product_data",
    "format_crypto_data",
    "format_banner_data"
]
