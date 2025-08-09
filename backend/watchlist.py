from flask import Blueprint, jsonify, request
import os

try:
    from watchlist_insights import Memory, smart_watchlist_insights
except ImportError:  # graceful fallback if module not present
    Memory = None
    smart_watchlist_insights = None

# For a simple dev server, we can use an in-memory set.
# For production, you'd replace this with a database linked to user accounts.
watchlist_db = set()

watchlist_bp = Blueprint('watchlist_bp', __name__)

# Shared in-memory log for insights (simple, process-local)
INSIGHTS_UNAVAILABLE = 'Insights memory unavailable'
_insights_memory = Memory(persist_path=os.path.join(os.path.dirname(__file__), 'watchlist_insights.log')) if Memory else None

@watchlist_bp.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    # In a real app, you'd fetch full market data for these symbols.
    return jsonify(list(watchlist_db))

@watchlist_bp.route('/api/watchlist', methods=['POST'])
def add_to_watchlist():
    data = request.get_json()
    if not data or 'symbol' not in data:
        return jsonify({'error': 'Symbol is required'}), 400
    
    symbol = data['symbol'].upper()
    watchlist_db.add(symbol)
    # Optionally record a structured log entry if price provided
    if _insights_memory and 'price' in data:
        try:
            price_val = float(data['price'])
            _insights_memory.add(f"User added {symbol} to their watchlist at ${price_val:.2f}")
        except (ValueError, TypeError):
            pass
    return jsonify({'message': f'{symbol} added to watchlist', 'watchlist': list(watchlist_db)}), 201

@watchlist_bp.route('/api/watchlist/<string:symbol>', methods=['DELETE'])
def remove_from_watchlist(symbol):
    symbol = symbol.upper()
    if symbol in watchlist_db:
        watchlist_db.remove(symbol)
        return jsonify({'message': f'{symbol} removed from watchlist', 'watchlist': list(watchlist_db)}), 200
    else:
        return jsonify({'error': f'{symbol} not in watchlist'}), 404


@watchlist_bp.route('/api/watchlist/insights', methods=['GET'])
def get_watchlist_insights():
    if not smart_watchlist_insights or not _insights_memory:
        return jsonify({'error': INSIGHTS_UNAVAILABLE}), 503
    result = smart_watchlist_insights(_insights_memory)
    return jsonify({'insights': result.split('\n') if result else [], 'raw': result})


@watchlist_bp.route('/api/watchlist/insights/log', methods=['POST'])
def add_watchlist_log():
    if not _insights_memory:
        return jsonify({'error': INSIGHTS_UNAVAILABLE}), 503
    data = request.get_json() or {}
    entry = data.get('entry')
    if not entry or not isinstance(entry, str):
        return jsonify({'error': 'entry (string) required'}), 400
    # Basic sanitization
    entry = entry.strip()[:500]
    _insights_memory.add(entry)
    return jsonify({'message': 'log added'}), 201


@watchlist_bp.route('/api/watchlist/insights/price', methods=['POST'])
def add_price_update():
    if not _insights_memory:
        return jsonify({'error': INSIGHTS_UNAVAILABLE}), 503
    data = request.get_json() or {}
    symbol = data.get('symbol')
    price = data.get('price')
    previous = data.get('previous')
    if not symbol or price is None or previous is None:
        return jsonify({'error': 'symbol, price, previous required'}), 400
    try:
        p = float(price)
        prev = float(previous)
        if prev == 0:
            return jsonify({'error': 'previous cannot be zero'}), 400
        delta_pct = ((p - prev) / prev) * 100
        _insights_memory.add(f"{symbol.upper()} is now at ${p:.2f} ({delta_pct:+.2f}%)")
        return jsonify({'message': 'price update logged', 'delta_pct': round(delta_pct, 2)})
    except (ValueError, TypeError):
        return jsonify({'error': 'invalid numeric values'}), 400


@watchlist_bp.route('/api/watchlist/insights/latest', methods=['POST'])
def latest_alerts_for_symbols():
    if not _insights_memory:
        return jsonify({'error': INSIGHTS_UNAVAILABLE}), 503
    data = request.get_json() or {}
    symbols = data.get('symbols')
    if not symbols or not isinstance(symbols, list):
        return jsonify({'error': 'symbols (list) required'}), 400
    result = {}
    for sym in symbols:
        last = _insights_memory.last_for_symbol(str(sym))
        if last:
            result[sym] = last
    return jsonify({'latest': result})