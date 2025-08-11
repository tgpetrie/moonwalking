"""Simple smoke test for critical backend endpoints.

Run while the server is already running (e.g. python backend/app.py) or set BASE_URL.
Pass criteria: 200 responses and minimal expected JSON keys/structure.
"""
import os
import sys
import time
import requests

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:5001")

ENDPOINTS = [
    ("/api/health", 200, ["status"]),
    ("/api/watchlist", 200, None),
    ("/api/watchlist/insights", 200, ["insights", "raw"]),
]

def fetch(path):
    url = BASE_URL.rstrip('/') + path
    try:
        r = requests.get(url, timeout=5)
        return r.status_code, r.json() if 'application/json' in r.headers.get('Content-Type','') else None
    except Exception as e:
        return None, {"error": str(e)}

def main():
    failures = []
    for path, expected_status, required_keys in ENDPOINTS:
        status, body = fetch(path)
        if status != expected_status:
            failures.append(f"{path}: expected {expected_status}, got {status}, body={body}")
            continue
        if required_keys and (not isinstance(body, dict) or any(k not in body for k in required_keys)):
            failures.append(f"{path}: missing required keys {required_keys} in body={body}")
    # Minimal functional write path: add & remove watchlist symbol
    sym = "TESTCOIN"
    try:
        add_resp = requests.post(BASE_URL + "/api/watchlist", json={"symbol": sym, "price": 1.23}, timeout=5)
        if add_resp.status_code != 201:
            failures.append(f"POST /api/watchlist add failed status={add_resp.status_code} body={add_resp.text}")
        rem_resp = requests.delete(BASE_URL + f"/api/watchlist/{sym}", timeout=5)
        if rem_resp.status_code not in (200,404):
            failures.append(f"DELETE /api/watchlist/{sym} failed status={rem_resp.status_code} body={rem_resp.text}")
    except Exception as e:
        failures.append(f"Watchlist add/remove error: {e}")

    if failures:
        print("SMOKE TEST FAILURES:")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("Smoke test passed")

if __name__ == "__main__":
    # optional small delay if starting right after server launch
    time.sleep(float(os.environ.get("SMOKE_START_DELAY", "0")))
    main()
