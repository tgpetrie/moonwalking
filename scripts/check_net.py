#!/usr/bin/env python3
import socket
import sys

import requests


def _tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def main() -> int:
    if not _tcp("api.coinbase.com", 443):
        print("BLOCKED")
        return 2
    try:
        resp = requests.get(
            "https://api.coinbase.com/v2/exchange-rates?currency=USD",
            timeout=4,
        )
    except requests.RequestException:
        print("BLOCKED")
        return 2
    print("OK" if resp.ok else "BLOCKED")
    return 0 if resp.ok else 2


if __name__ == "__main__":
    sys.exit(main())
