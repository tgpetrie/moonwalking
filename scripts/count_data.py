#!/usr/bin/env python3
"""
Quick endpoint inspector.

Usage:
    ./scripts/count_data.py http://127.0.0.1:5003/api/component/bottom-banner-scroll
    ./scripts/count_data.py /api/component/gainers-table-1min
    ./scripts/count_data.py                   # defaults to local health

It:
- fetches JSON
- prints top-level keys
- if there's a `data` array, prints its length
- exits non-zero on non-200
"""

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:5003"


def fetch_json(url: str):
    if url.startswith("/"):
        url = BASE + url
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else f"{BASE}/api/health"
    try:
        data = fetch_json(url)
    except Exception as e:
        print(f"ERROR: failed to fetch {url}: {e}", file=sys.stderr)
        sys.exit(1)

    if isinstance(data, dict):
        keys = ", ".join(data.keys())
        print(f"OK {url}")
        print(f"- keys: {keys}")
        if "data" in data and isinstance(data["data"], list):
            print(f"- data length: {len(data['data'])}")
    elif isinstance(data, list):
        print(f"OK {url}")
        print(f"- list length: {len(data)}")
    else:
        print(f"OK {url}")
        print(f"- type: {type(data)}")


if __name__ == "__main__":
    main()
