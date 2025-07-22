from flask import Blueprint, jsonify, request

# For a simple dev server, we can use an in-memory set.
# For production, you'd replace this with a database linked to user accounts.
watchlist_db = set()

watchlist_bp = Blueprint('watchlist_bp', __name__)

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
    return jsonify({'message': f'{symbol} added to watchlist', 'watchlist': list(watchlist_db)}), 201

@watchlist_bp.route('/api/watchlist/<string:symbol>', methods=['DELETE'])
def remove_from_watchlist(symbol):
    symbol = symbol.upper()
    if symbol in watchlist_db:
        watchlist_db.remove(symbol)
        return jsonify({'message': f'{symbol} removed from watchlist', 'watchlist': list(watchlist_db)}), 200
    else:
        return jsonify({'error': f'{symbol} not in watchlist'}), 404