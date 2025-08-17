import os
import argparse
import socket
import subprocess
import sys
from flask import Flask, jsonify, request, g
from flask_cors import CORS
import requests
import time
import threading
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from datetime import datetime, timedelta

from watchlist import watchlist_bp, watchlist_db
try:
    # optional insight memory (may not exist early in startup)
    from watchlist import _insights_memory as INSIGHTS_MEMORY
except Exception:
    INSIGHTS_MEMORY = None

COINBASE_PRODUCTS_URL = "https://api.exchange.coinbase.com/products"
ERROR_NO_DATA = "No data available"
INSIGHTS_MIN_NET_CHANGE_PCT = float(os.environ.get('INSIGHTS_MIN_NET_CHANGE_PCT', '3'))  # was 5
INSIGHTS_MIN_STEP_CHANGE_PCT = float(os.environ.get('INSIGHTS_MIN_STEP_CHANGE_PCT', '1'))  # was 2
VOLUME_SPIKE_THRESHOLD = float(os.environ.get('INSIGHTS_VOLUME_SPIKE_THRESHOLD', '5000000'))  # 5M 24h vol
VOLUME_SPIKE_MIN_CHANGE_PCT = float(os.environ.get('INSIGHTS_VOLUME_SPIKE_MIN_CHANGE_PCT', '8'))  # 8% move + volume

# (app is created later once logging/config are setup)

from config import CONFIG
from logging_config import setup_logging
from logging_config import log_config as log_config_with_param
from utils import find_available_port

# Production-ready imports
from dotenv import load_dotenv
# Temporarily disable sentry for Python 3.13 compatibility
try:
    # import sentry_sdk
    # from sentry_sdk.integrations.flask import FlaskIntegration
    SENTRY_AVAILABLE = False  # Disabled for compatibility
except ImportError:
    SENTRY_AVAILABLE = False

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False

try:
    from flask_talisman import Talisman
    TALISMAN_AVAILABLE = True
except ImportError:
    TALISMAN_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Load environment variables
load_dotenv()

# ---------------------------------------------------------------------------------
# Utility: best-effort commit SHA for diagnostics (/api/server-info)
# ---------------------------------------------------------------------------------
def _get_commit_sha() -> str:
    """Return a short commit SHA if available via env or local git. Best effort only."""
    try:
        # Prefer explicit env (e.g., set by CI/CD)
        sha = os.environ.get('COMMIT_SHA') or os.environ.get('GIT_COMMIT')
        if sha:
            return str(sha)[:12]
        # Try git (may not exist in container)
        out = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], stderr=subprocess.DEVNULL)
        return out.decode('utf-8').strip()
    except Exception:
        return 'unknown'

# Initialize Sentry for error tracking in production (disabled for compatibility)
# if SENTRY_AVAILABLE and os.environ.get('SENTRY_DSN'):
#     sentry_sdk.init(
#         dsn=os.environ.get('SENTRY_DSN'),
#         integrations=[FlaskIntegration()],
#         traces_sample_rate=0.1,
#         environment=os.environ.get('ENVIRONMENT', 'production')
#     )
from social_sentiment import get_social_sentiment
# CBMo4ers Crypto Dashboard Backend
# Data Sources: Public Coinbase Exchange API + CoinGecko (backup)
# No API keys required - uses public market data only

# Setup logging
setup_logging()

# Log configuration
log_config_with_param(CONFIG)

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

@app.route('/api/health')
def api_health():
    """Lightweight health alias (faster than full server-info)."""
    return jsonify({
        'status': 'ok',
        'uptime_seconds': round(time.time() - startup_time, 2),
        'errors_5xx': _ERROR_STATS['5xx']
    })

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
                """Fetch ticker data for a single product"""
                symbol = product["id"]
                ticker_url = f"https://api.exchange.coinbase.com/products/{symbol}/ticker"
                try:
                    ticker_response = requests.get(ticker_url, timeout=1.5)
                    if ticker_response.status_code == 200:
                        ticker_data = ticker_response.json()
                        price = float(ticker_data.get('price', 0))
                        if price > 0:
                            return symbol, price
                except Exception as ticker_error:
                    logging.warning(f"Failed to get ticker for {symbol}: {ticker_error}")
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
    """Format 3-minute crypto data for frontend with detailed price tracking.
    Includes legacy aliases (change3m, prev3m, current_price, initial_price_3min, price_change_percentage_3min)
    so older frontend code continues to work.
    """
    return [
        {
            "symbol": coin["symbol"],
            # canonical keys used by newer components
            "current": coin["current_price"],
            "initial_3min": coin["initial_price_3min"],
            "gain": coin["price_change_percentage_3min"],
            "interval_minutes": round(coin["actual_interval_minutes"], 1),
            # aliases for backward-compat with earlier frontend mapping
            "current_price": coin["current_price"],
            "initial_price_3min": coin["initial_price_3min"],
            "price_change_percentage_3min": coin["price_change_percentage_3min"],
            "change3m": coin["price_change_percentage_3min"],
            "prev3m": coin["initial_price_3min"],
        }
        for coin in crypto_data
    ]

def format_crypto_data_1min(crypto_data):
    """Format 1-minute crypto data with legacy aliases for compatibility."""
    return [
        {
            "symbol": coin["symbol"],
            # canonical keys
            "current": coin["current_price"],
            "initial_1min": coin["initial_price_1min"],
            "gain": coin["price_change_percentage_1min"],
            "interval_minutes": round(coin["actual_interval_minutes"], 1),
            # aliases for older frontend
            "current_price": coin["current_price"],
            "initial_price_1min": coin["initial_price_1min"],
            "price_change_percentage_1min": coin["price_change_percentage_1min"],
            "change1m": coin["price_change_percentage_1min"],
            "prev1m": coin["initial_price_1min"],
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
            
        # Format specifically for top banner - current price and 1h change focus
        top_banner_data = []
        for coin in banner_data[:20]:  # Top 20 for scrolling
            top_banner_data.append({
                "symbol": coin["symbol"],
                "current_price": coin["current_price"],
                "price_change_1h": coin["price_change_1h"],
                "market_cap": coin.get("market_cap", 0)
            })
        
        return jsonify({
            "banner_data": top_banner_data,
            "type": "top_banner",
            "count": len(top_banner_data),
            "last_updated": datetime.now().isoformat()
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
        
        # Format specifically for bottom banner - volume and 1h change focus
        bottom_banner_data = []
        for coin in volume_sorted[:20]:  # Top 20 by volume
            bottom_banner_data.append({
                "symbol": coin["symbol"],
                "volume_24h": coin["volume_24h"],
                "price_change_1h": coin["price_change_1h"],
                "current_price": coin["current_price"]
            })
        
        return jsonify({
            "banner_data": bottom_banner_data,
            "type": "bottom_banner", 
            "count": len(bottom_banner_data),
            "last_updated": datetime.now().isoformat()
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
        
        # Format specifically for tables with 3-minute data
        tables_data = {
            "gainers": gainers[:15],  # Top 15 gainers
            "losers": losers[:15],    # Top 15 losers
            "type": "tables_3min",
            "count": {
                "gainers": len(gainers[:15]),
                "losers": len(losers[:15])
            },
            "last_updated": datetime.now().isoformat()
        }
        
        return jsonify(tables_data)
    except Exception as e:
        logging.error(f"Error in tables endpoint: {e}")
        return jsonify({"error": str(e)}), 500

# =============================================================================
# INDIVIDUAL COMPONENT ENDPOINTS - Each component gets its own unique data
# =============================================================================

@app.route('/api/component/top-banner-scroll')
def get_top_banner_scroll():
    """Individual endpoint for top scrolling banner - 1-hour price change data"""
    try:
        # Get 1-hour price change data from 24h movers API
        banner_data = get_24h_top_movers()
        if not banner_data:
            return jsonify({"error": ERROR_NO_DATA}), 503
            
        # Sort by 1-hour price change for top banner
        hour_sorted = sorted(banner_data, key=lambda x: abs(x.get("price_change_1h", 0)), reverse=True)
        
        top_scroll_data = []
        for coin in hour_sorted[:20]:  # Top 20 by 1-hour price change
            sym = coin["symbol"]
            ch = float(coin.get("price_change_1h", 0) or 0)
            prev = one_hour_price_trends.get(sym, {"last": ch, "streak": 0, "last_dir": "flat", "score": 0.0})
            direction = "up" if ch > prev["last"] else ("down" if ch < prev["last"] else "flat")
            streak = prev["streak"] + 1 if direction != "flat" and direction == prev["last_dir"] else (1 if direction != "flat" else prev["streak"])
            score = round(prev["score"] * 0.9 + ch * 0.1, 3)
            one_hour_price_trends[sym] = {"last": ch, "streak": streak, "last_dir": direction, "score": score}
            _maybe_fire_trend_alert('1h_price', sym, direction, streak, score)
            top_scroll_data.append({
                "symbol": coin["symbol"],
                "current_price": coin["current_price"],
                "price_change_1h": coin["price_change_1h"],  # 1-hour price change
                "initial_price_1h": coin["initial_price_1h"],
                "market_cap": coin.get("market_cap", 0),
                "sparkline_trend": "up" if coin["price_change_1h"] > 0 else "down",
                "trend_direction": direction,
                "trend_streak": streak,
                "trend_score": score
            })
        
        return jsonify({
            "component": "top_banner_scroll",
            "data": top_scroll_data,
            "count": len(top_scroll_data),
            "time_frame": "1_hour",
            "focus": "price_change",
            "scroll_speed": "medium",
            "update_interval": 60000,  # 1 minute updates for 1-hour data
            "last_updated": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Error in top banner scroll endpoint: {e}")
        return jsonify({"error": str(e)}), 500

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
                "change3m": coin["gain"],  # legacy alias for older frontend
                "initial_price_3min": coin["initial_3min"],  # Use correct field name
                "prev3m": coin["initial_3min"],  # legacy alias for older frontend
                "actual_interval_minutes": coin.get("interval_minutes", 3),  # Use correct field name
                "trend_direction": direction,
                "trend_streak": streak,
                "trend_score": score,
                "momentum": "strong" if coin["gain"] > 5 else "moderate",
                "alert_level": "high" if coin["gain"] > 10 else "normal",
                # additional alias fields
                "price": coin["current"],
                "prev": coin["initial_3min"],
                "change": coin["gain"],
                "percent_change_3m": coin["gain"],
                "prev_price_3m": coin["initial_3min"],
                "percentage": coin["gain"],
                "previous": coin["initial_3min"],
            })
        
        return jsonify({
            "component": "gainers_table",
            "data": gainers_table_data,
            "count": len(gainers_table_data),
            "table_type": "gainers",
            "time_frame": "3_minutes",
            "update_interval": 3000,
            "last_updated": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Error in gainers table endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/component/losers-table')
def get_losers_table():
    """Individual endpoint for losers table - 3-minute data only"""
    try:
        data = get_crypto_data()
        if not data:
            return jsonify({"error": ERROR_NO_DATA}), 503
            
        losers = data.get('losers', [])
        
        # Enhanced formatting specifically for losers table
        losers_table_data = []
        for i, coin in enumerate(losers[:20]):  # Top 20 losers
            sym = coin["symbol"]
            g = float(coin.get("gain", 0) or 0)
            prev = three_minute_trends.get(sym, {"last": g, "streak": 0, "last_dir": "flat", "score": 0.0})
            direction = "up" if g > prev["last"] else ("down" if g < prev["last"] else "flat")
            streak = prev["streak"] + 1 if direction != "flat" and direction == prev["last_dir"] else (1 if direction != "flat" else prev["streak"])
            score = round(prev["score"] * 0.8 + g * 0.2, 3)
            three_minute_trends[sym] = {"last": g, "streak": streak, "last_dir": direction, "score": score}
            losers_table_data.append({
                "rank": i + 1,
                "symbol": coin["symbol"],
                "current_price": coin["current"],  # Use correct field name
                "price_change_percentage_3min": coin["gain"],  # Use correct field name (negative for losers)
                "change3m": coin["gain"],  # legacy alias for older frontend
                "initial_price_3min": coin["initial_3min"],  # Use correct field name
                "prev3m": coin["initial_3min"],  # legacy alias for older frontend
                "actual_interval_minutes": coin.get("interval_minutes", 3),  # Use correct field name
                "trend_direction": direction,
                "trend_streak": streak,
                "trend_score": score,
                "momentum": "strong" if coin["gain"] < -5 else "moderate",
                "alert_level": "high" if coin["gain"] < -10 else "normal",
                # additional alias fields
                "price": coin["current"],
                "prev": coin["initial_3min"],
                "change": coin["gain"],
                "percent_change_3m": coin["gain"],
                "prev_price_3m": coin["initial_3min"],
                "percentage": coin["gain"],
                "previous": coin["initial_3min"],
            })
        
        return jsonify({
            "component": "losers_table",
            "data": losers_table_data,
            "count": len(losers_table_data),
            "table_type": "losers",
            "time_frame": "3_minutes",
            "update_interval": 3000,
            "last_updated": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Error in losers table endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/component/top-movers-bar')
def get_top_movers_bar():
    """Individual endpoint for top movers horizontal bar - 3min focus"""
    try:
        # Get 3-minute data
        data = get_crypto_data()
        if not data:
            return jsonify({"error": ERROR_NO_DATA}), 503
            
        # Use top24h which is already a mix of top gainers and losers from 3-min data
        top_movers_3min = data.get('top24h', [])
        
        # Format specifically for horizontal moving bar
        top_movers_data = []
        for coin in top_movers_3min[:15]:  # Perfect amount for horizontal scroll
            top_movers_data.append({
                "symbol": coin["symbol"],
                "current_price": coin["current"],
                "price_change_3min": coin["gain"],  # 3-minute change
                "initial_price_3min": coin["initial_3min"],
                "interval_minutes": coin.get("interval_minutes", 3),
                "bar_color": "green" if coin["gain"] > 0 else "red",
                "momentum": "strong" if abs(coin["gain"]) > 5 else "moderate"
            })
        
        return jsonify({
            "component": "top_movers_bar",
            "data": top_movers_data,
            "count": len(top_movers_data),
            "animation": "horizontal_scroll",
            "time_frame": "3_minutes",
            "update_interval": 3000,
            "last_updated": datetime.now().isoformat()
        })
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
        data = get_crypto_data_1min()
        if not data:
            return jsonify({"error": "No 1-minute data available"}), 503
            
        gainers = data.get('gainers', [])
        
        gainers_table_data = []
        for i, coin in enumerate(gainers[:20]):  # Top 20 gainers
            gainers_table_data.append({
                "rank": i + 1,
                "symbol": coin["symbol"],
                "current_price": coin["current"],
                "price_change_percentage_1min": coin["gain"],
                "initial_price_1min": coin["initial_1min"],
                "actual_interval_minutes": coin.get("interval_minutes", 1),
                "peak_gain": coin.get("peak_gain", coin["gain"]),
                "trend_direction": coin.get("trend_direction", "flat"),
                "trend_streak": coin.get("trend_streak", 0),
                "trend_score": coin.get("trend_score", 0.0),
                "trend_delta": coin.get("trend_delta", 0.0),
                "momentum": "strong" if coin["gain"] > 5 else "moderate",
                "alert_level": "high" if coin["gain"] > 10 else "normal"
            })
        
        return jsonify({
            "component": "gainers_table_1min",
            "data": gainers_table_data,
            "count": len(gainers_table_data),
            "table_type": "gainers",
            "time_frame": "1_minute",
            "update_interval": 10000, # 10 seconds for 1-min data
            "last_updated": datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"Error in 1-minute gainers table endpoint: {e}")
        return jsonify({"error": str(e)}), 500
# =============================================================================

# Add startup time tracking
# Add startup time tracking for uptime calculation

@app.route('/')
def root():
    """Root endpoint"""
    return jsonify({
        "service": "CBMo4ers Crypto Dashboard Backend",
        "status": "running",
        "version": "3.0.0",
        "description": "Individual component endpoints with correct time frames",
        "individual_component_endpoints": [
            "/api/component/top-banner-scroll",     # Top scrolling banner - 1-hour PRICE change
            "/api/component/bottom-banner-scroll",  # Bottom scrolling banner - 1-hour VOLUME change  
            "/api/component/gainers-table",         # Gainers table - 3-minute data (main feature)
            "/api/component/losers-table",          # Losers table - 3-minute data (main feature)
            "/api/component/top-movers-bar"         # Horizontal top movers bar - 3-minute data
        ],
        "time_frame_specification": {
            "top_banner": "1-hour price change data",
            "bottom_banner": "1-hour volume change data", 
            "main_tables": "3-minute gainers/losers data (key feature)",
            "top_movers_bar": "3-minute data"
        },
        "legacy_endpoints": [
            "/api/health",
            "/api/banner-top",     # Legacy: Top banner
            "/api/banner-bottom",  # Legacy: Bottom banner
            "/api/tables-3min",    # Legacy: Tables
            "/api/crypto",         # Legacy: Combined data
            "/api/banner-1h",      # Legacy: Banner data
            "/api/chart/BTC-USD",
            "/api/watchlist",
            "/api/config"
        ]
    })

@app.route('/api/crypto')
def get_crypto_endpoint():
    """Main crypto data endpoint with 3-minute tracking"""
    try:
        data = get_crypto_data()
        if data:
            return jsonify(data)
        else:
            return jsonify({"error": "No data available"}), 503
    except Exception as e:
        logging.error(f"Error in crypto endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/banner-1h')
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

@app.route('/api/config')
def get_config():
    """Get current configuration"""
    return jsonify({
        "config": CONFIG,
        "cache_status": {
            "has_data": cache["data"] is not None,
            "age_seconds": time.time() - cache["timestamp"] if cache["timestamp"] > 0 else 0,
            "ttl": cache["ttl"]
        },
        "price_history_status": {
            "symbols_tracked": len(price_history),
            "max_history_per_symbol": CONFIG['MAX_PRICE_HISTORY']
        },
        "one_minute_status": {
            "enabled": CONFIG.get('ENABLE_1MIN', True),
            "last_generated_age": time.time() - one_minute_cache['timestamp'] if one_minute_cache['timestamp'] else None,
            "refresh_window_seconds": CONFIG.get('ONE_MIN_REFRESH_SECONDS'),
            "has_snapshot": one_minute_cache['data'] is not None,
            "enter_threshold_pct": CONFIG.get('ONE_MIN_ENTER_PCT'),
            "stay_threshold_pct": CONFIG.get('ONE_MIN_STAY_PCT'),
            "dwell_seconds": CONFIG.get('ONE_MIN_DWELL_SECONDS'),
            "max_coins": CONFIG.get('ONE_MIN_MAX_COINS'),
            "retained_symbols": len(one_minute_persistence['entries'])
        }
    })

@app.route('/api/config', methods=['POST'])
def update_config_endpoint():
    """Update configuration at runtime"""
    try:
        new_config = request.get_json()
        if not new_config:
            return jsonify({"error": "No configuration provided"}), 400
        
        update_config(new_config)
        return jsonify({
            "message": "Configuration updated successfully",
            "new_config": CONFIG
        })
    except Exception as e:
        logging.error(f"Error updating config: {e}")
        return jsonify({"error": str(e)}), 500

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

__all__ = [
    "process_product_data",
    "format_crypto_data",
    "format_banner_data"
]

