import os
import argparse
import socket
import subprocess
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import time
import threading
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from datetime import datetime, timedelta

from watchlist import watchlist_bp

# Flask App Setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'crypto-dashboard-secret')

# Register blueprints
app.register_blueprint(watchlist_bp)

from config import CONFIG
from logging_config import setup_logging
from logging_config import log_config as log_config_with_param
from utils import find_available_port

# Production-ready imports
from dotenv import load_dotenv
try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    SENTRY_AVAILABLE = True
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

# Initialize Sentry for error tracking in production
if SENTRY_AVAILABLE and os.environ.get('SENTRY_DSN'):
    sentry_sdk.init(
        dsn=os.environ.get('SENTRY_DSN'),
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get('ENVIRONMENT', 'production')
    )
# CBMo4ers Crypto Dashboard Backend
# Data Sources: Public Coinbase Exchange API + CoinGecko (backup)
# No API keys required - uses public market data only

# Setup logging
setup_logging()

# Log configuration
log_config_with_param(CONFIG)

# Flask App Setup
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
        products_url = "https://api.exchange.coinbase.com/products"
        products_response = requests.get(products_url, timeout=CONFIG['API_TIMEOUT'])
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
    """Calculate price changes over dynamic intervals"""
    current_time = time.time()
    interval_seconds = CONFIG['INTERVAL_MINUTES'] * 60
    
    # Update price history with current prices
    for symbol, price in current_prices.items():
        if price > 0:
            price_history[symbol].append((current_time, price))
    
    # Calculate changes for each symbol
    formatted_data = []
    for symbol, price in current_prices.items():
        if price <= 0:
            continue
            
        history = price_history[symbol]
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
    """Fetch 24h top movers from Coinbase as backup (OPTIMIZED)"""
    try:
        products_url = "https://api.exchange.coinbase.com/products"
        products_response = requests.get(products_url, timeout=CONFIG['API_TIMEOUT'])
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
            return jsonify({"error": "No data available"}), 503
            
        # Sort by 1-hour price change for top banner
        hour_sorted = sorted(banner_data, key=lambda x: abs(x.get("price_change_1h", 0)), reverse=True)
        
        top_scroll_data = []
        for coin in hour_sorted[:20]:  # Top 20 by 1-hour price change
            top_scroll_data.append({
                "symbol": coin["symbol"],
                "current_price": coin["current_price"],
                "price_change_1h": coin["price_change_1h"],  # 1-hour price change
                "initial_price_1h": coin["initial_price_1h"],
                "market_cap": coin.get("market_cap", 0),
                "sparkline_trend": "up" if coin["price_change_1h"] > 0 else "down"
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
            return jsonify({"error": "No data available"}), 503
            
        # Sort by 24h volume for bottom banner (as we don't have hourly volume data)
        volume_sorted = sorted(banner_data, key=lambda x: x.get("volume_24h", 0), reverse=True)
        
        bottom_scroll_data = []
        for coin in volume_sorted[:20]:  # Top 20 by volume
            # Calculate estimated volume change (using price change as proxy)
            volume_change_estimate = coin["price_change_1h"] * 0.5  # Volume often correlates with price movement
            
            bottom_scroll_data.append({
                "symbol": coin["symbol"],
                "current_price": coin["current_price"],
                "volume_24h": coin["volume_24h"],
                "price_change_1h": coin["price_change_1h"],  # 1-hour change
                "volume_change_estimate": volume_change_estimate,
                "volume_category": "high" if coin["volume_24h"] > 10000000 else "medium" if coin["volume_24h"] > 1000000 else "low"
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
            return jsonify({"error": "No data available"}), 503
            
        gainers = data.get('gainers', [])
        
        # Enhanced formatting specifically for gainers table
        gainers_table_data = []
        for i, coin in enumerate(gainers[:20]):  # Top 20 gainers
            gainers_table_data.append({
                "rank": i + 1,
                "symbol": coin["symbol"],
                "current_price": coin["current"],  # Use correct field name
                "price_change_percentage_3min": coin["gain"],  # Use correct field name
                "initial_price_3min": coin["initial_3min"],  # Use correct field name
                "actual_interval_minutes": coin.get("interval_minutes", 3),  # Use correct field name
                "momentum": "strong" if coin["gain"] > 5 else "moderate",
                "alert_level": "high" if coin["gain"] > 10 else "normal"
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
            return jsonify({"error": "No data available"}), 503
            
        losers = data.get('losers', [])
        
        # Enhanced formatting specifically for losers table
        losers_table_data = []
        for i, coin in enumerate(losers[:20]):  # Top 20 losers
            losers_table_data.append({
                "rank": i + 1,
                "symbol": coin["symbol"],
                "current_price": coin["current"],  # Use correct field name
                "price_change_percentage_3min": coin["gain"],  # Use correct field name (negative for losers)
                "initial_price_3min": coin["initial_3min"],  # Use correct field name
                "actual_interval_minutes": coin.get("interval_minutes", 3),  # Use correct field name
                "momentum": "strong" if coin["gain"] < -5 else "moderate",
                "alert_level": "high" if coin["gain"] < -10 else "normal"
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
            return jsonify({"error": "No data available"}), 503
            
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

# =============================================================================
# EXISTING ENDPOINTS (Updated root to show new individual endpoints)

def get_crypto_data_1min():
    """Main function to fetch and process 1-minute crypto data"""
    current_time = time.time()
    
    # No cache for 1-min data, always fetch fresh
    
    try:
        # Get current prices for 1-minute calculations
        current_prices = get_current_prices()
        if not current_prices:
            logging.warning("No current prices available for 1-min data")
            return None
            
        # Calculate 1-minute interval changes
        crypto_data = calculate_1min_changes(current_prices)
        
        if not crypto_data:
            logging.warning(f"No 1-min crypto data available after calculation - {len(current_prices)} current prices, {len(price_history_1min)} symbols with history")
            return None
        
        # Separate gainers and losers based on 1-minute changes
        gainers = [coin for coin in crypto_data if coin.get("price_change_percentage_1min", 0) > 0]
        losers = [coin for coin in crypto_data if coin.get("price_change_percentage_1min", 0) < 0]
        
        # Sort by 1-minute percentage change
        gainers.sort(key=lambda x: x["price_change_percentage_1min"], reverse=True)
        losers.sort(key=lambda x: x["price_change_percentage_1min"])
        
        result = {
            "gainers": format_crypto_data_1min(gainers[:15]),
            "losers": format_crypto_data_1min(losers[:15]),
        }
        
        logging.info(f"Successfully processed 1-min data: {len(result['gainers'])} gainers, {len(result['losers'])} losers")
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

@app.route('/api/watchlist')
def get_watchlist():
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
    """Get server information including port and status"""
    return jsonify({
        "port": CONFIG['PORT'],
        "host": CONFIG['HOST'],
        "debug": CONFIG['DEBUG'],
        "status": "running",
        "cors_origins": cors_origins,
        "cache_ttl": CONFIG['CACHE_TTL'],
        "update_interval": CONFIG['UPDATE_INTERVAL'],
        "version": "3.0.0",
        "timestamp": datetime.now().isoformat()
    })

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

# =============================================================================

def background_crypto_updates():
    """Background thread to update cache periodically"""
    while True:
        try:
            # Update 3-min data cache
            data_3min = get_crypto_data()
            if data_3min:
                logging.info(f"3-min cache updated: {len(data_3min['gainers'])} gainers, {len(data_3min['losers'])} losers, {len(data_3min['banner'])} banner items")

            # Also fetch current prices to update 1-min history
            current_prices = get_current_prices()
            if current_prices:
                # This will update price_history_1min deque
                calculate_1min_changes(current_prices)
                logging.info(f"1-min price history updated with {len(current_prices)} new prices.")

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
            logging.error(f"1. python3 app.py --kill-port")
            logging.error(f"2. python3 app.py --auto-port")
            logging.error(f"3. python3 app.py --port 5002")
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

