"""Check the running Railway service through its public domains, without credentials.

This verifies current availability, not which Git commit Railway deployed.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen


def probe(base):
    for path in ("/", "/api/health", "/data"):
        request = Request(base + path, headers={"User-Agent": "Moonwalking-Smoke/1.0"})
        with urlopen(request, timeout=25) as response:
            if response.status != 200:
                raise RuntimeError(f"{base}{path}: HTTP {response.status}")
            content = response.read().decode("utf-8")
            if path == "/":
                if "<html" not in content.lower() or "/assets/" not in content:
                    raise RuntimeError(f"{base}: built frontend is missing")
            else:
                payload = json.loads(content)
                if path == "/api/health" and payload.get("status") != "ok":
                    raise RuntimeError(f"{base}: health is not ok")
                if path == "/data":
                    for key in (
                        "gainers_1m", "gainers_3m", "losers_3m",
                        "banner_1h_price", "banner_1h_volume",
                    ):
                        if not isinstance(payload.get(key), list):
                            raise RuntimeError(f"{base}: board array {key} is missing")
            print(f"PASS {base}{path}")


if __name__ == "__main__":
    origins = (
        "https://bhabit-mooners-production.up.railway.app",
        "https://bhabit.net",
        "https://www.bhabit.net",
    )
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(probe, origins))
    print("Running service is healthy. Confirm its commit in Railway before accepting a release.")
