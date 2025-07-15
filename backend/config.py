import os

CONFIG = {
    'CACHE_TTL': int(os.environ.get('CACHE_TTL', 60)),
    'INTERVAL_MINUTES': int(os.environ.get('INTERVAL_MINUTES', 3)),
    'MAX_PRICE_HISTORY': int(os.environ.get('MAX_PRICE_HISTORY', 20)),
    'PORT': int(os.environ.get('PORT', 5001)),  # Fixed stable port for development
    'HOST': os.environ.get('HOST', '0.0.0.0'),
    'DEBUG': os.environ.get('DEBUG', 'False').lower() == 'true',
    'UPDATE_INTERVAL': int(os.environ.get('UPDATE_INTERVAL', 60)),
    'MAX_COINS_PER_CATEGORY': int(os.environ.get('MAX_COINS_PER_CATEGORY', 15)),
    'MIN_VOLUME_THRESHOLD': int(os.environ.get('MIN_VOLUME_THRESHOLD', 1000000)),
    'MIN_CHANGE_THRESHOLD': float(os.environ.get('MIN_CHANGE_THRESHOLD', 1.0)),
    'API_TIMEOUT': int(os.environ.get('API_TIMEOUT', 10)),
    'CHART_DAYS_LIMIT': int(os.environ.get('CHART_DAYS_LIMIT', 30)),
}
