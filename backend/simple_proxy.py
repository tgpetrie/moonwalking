#!/usr/bin/env python3
"""
Minimal Flask proxy to forward sentiment requests from frontend to sentiment API
"""
import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5173", "http://localhost:5173"])

SENTIMENT_API_URL = os.getenv("SENTIMENT_PIPELINE_URL")


def _require_sentiment_url():
    if not SENTIMENT_API_URL:
        return None, (jsonify({"error": "SENTIMENT_PIPELINE_URL not set"}), 503)
    return SENTIMENT_API_URL.rstrip("/"), None

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "service": "proxy"})

@app.route('/api/sentiment/latest')
def sentiment_latest():
    """Proxy to sentiment API"""
    symbol = request.args.get('symbol', 'BTC')
    fresh = request.args.get('fresh', '0')

    try:
        base, err = _require_sentiment_url()
        if err:
            return err
        # Forward to sentiment API
        url = f"{base}/sentiment/latest"
        params = {'symbol': symbol}
        if fresh == '1':
            params['fresh'] = '1'

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sentiment/tiered')
def sentiment_tiered():
    """Proxy tiered sentiment"""
    symbol = request.args.get('symbol', 'BTC')
    try:
        base, err = _require_sentiment_url()
        if err:
            return err
        url = f"{base}/sentiment/tiered"
        response = requests.get(url, params={'symbol': symbol}, timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sentiment/sources')
def sentiment_sources():
    """Proxy sentiment sources"""
    try:
        base, err = _require_sentiment_url()
        if err:
            return err
        url = f"{base}/sentiment/sources"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sentiment/health')
def sentiment_health():
    """Proxy sentiment health"""
    try:
        base, err = _require_sentiment_url()
        if err:
            return err
        url = f"{base}/health"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e), "status": "unhealthy"}), 503

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5003))
    app.run(host='127.0.0.1', port=port, debug=True)
