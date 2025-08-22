from flask import Flask, jsonify
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app)

@app.get("/api/health")
def health():
    return jsonify({"ok": True, "ts": int(time.time())})

@app.get("/api/server-info")
def server_info():
    return jsonify({
        "name": "BHABIT dev server",
        "version": "0.0.1",
        "ts": int(time.time()),
    })

# ----- banners -----
@app.get("/api/component/top-banner-scroll")
def top_banner():
    return jsonify({
        "items": [
            {"id": 1, "text": "BTC breaks key level"},
            {"id": 2, "text": "ETH funding flips positive"},
            {"id": 3, "text": "ALTS rotating into strength"},
        ]
    })

@app.get("/api/component/bottom-banner-scroll")
def bottom_banner():
    return jsonify({
        "items": [
            {"id": "w1", "text": "Your watchlist: BTC +0.8%"},
            {"id": "w2", "text": "SOL +2.1% in last hour"},
            {"id": "w3", "text": "OP heavy volume spike"},
        ]
    })

# ----- tables -----
@app.get("/api/component/gainers-table-1min")
def gainers_1m():
    rows = [
        {"rank": 1, "symbol": "SOL", "price": 143.23, "delta_1m": 0.006},
        {"rank": 2, "symbol": "OP",  "price": 2.31,   "delta_1m": 0.004},
        {"rank": 3, "symbol": "SEI", "price": 0.61,   "delta_1m": 0.003},
        {"rank": 4, "symbol": "ENA", "price": 0.38,   "delta_1m": 0.003},
        {"rank": 5, "symbol": "RNDR","price": 9.14,   "delta_1m": 0.002},
        {"rank": 6, "symbol": "TIA", "price": 7.82,   "delta_1m": 0.002},
        {"rank": 7, "symbol": "BTC", "price": 67750,  "delta_1m": 0.001},
        {"rank": 8, "symbol": "ETH", "price": 3550,   "delta_1m": 0.001},
        {"rank": 9, "symbol": "ARK", "price": 2.01,   "delta_1m": 0.001},
        {"rank":10, "symbol": "DOGE","price": 0.12,   "delta_1m": 0.001},
        {"rank":11, "symbol": "ADA", "price": 0.43,   "delta_1m": 0.001},
        {"rank":12, "symbol": "FTM", "price": 0.58,   "delta_1m": 0.001},
        {"rank":13, "symbol": "NEAR","price": 6.01,   "delta_1m": 0.001},
        {"rank":14, "symbol": "TON", "price": 6.28,   "delta_1m": 0.001},
        {"rank":15, "symbol": "WIF", "price": 1.41,   "delta_1m": 0.001},
        {"rank":16, "symbol": "JUP", "price": 0.82,   "delta_1m": 0.001},
    ]
    return jsonify({"items": rows})

@app.get("/api/component/gainers-table")
def gainers_3m():
    rows = [
        {"rank": 1, "symbol": "SOL", "price": 143.23, "delta_3m": 0.015},
        {"rank": 2, "symbol": "OP",  "price": 2.31,   "delta_3m": 0.012},
        {"rank": 3, "symbol": "SEI", "price": 0.61,   "delta_3m": 0.010},
        {"rank": 4, "symbol": "ENA", "price": 0.38,   "delta_3m": 0.009},
    ]
    return jsonify({"items": rows})

@app.get("/api/component/losers-table")
def losers_3m():
    rows = [
        {"symbol": "ARB", "price": 0.94, "delta_3m": -0.012},
        {"symbol": "SUI", "price": 1.12, "delta_3m": -0.010},
        {"symbol": "APE", "price": 0.86, "delta_3m": -0.009},
        {"symbol": "BCH", "price": 392.1,"delta_3m": -0.008},
    ]
    return jsonify({"items": rows})

# ----- optional: watchlist latest -----
@app.post("/api/watchlist/insights/latest")
def w_latest():
    # return empty mapping to satisfy callers
    return jsonify({"latest": {}})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)