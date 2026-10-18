"""NEW COPY/ADAPTATION of backfill_research_candles.py: tiny unauthenticated GET-only prototypes.
One global request scheduler, >=1.1 seconds between request starts, no redirects,
no credentials, private paths, environment configuration, exchange SDKs or production.
"""

import datetime, hashlib, json, pathlib, time, sys, io, gzip, tarfile, zipfile, csv
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

ROOT = pathlib.Path(__file__).resolve().parent
MODE = sys.argv[1] if __name__ == "__main__" and len(sys.argv) > 1 else "standard"
OUT = pathlib.Path(".runtime/redteam_20261018") / (
    "public_samples_history"
    if MODE == "history"
    else (
        "public_samples_archives"
        if MODE == "archive_samples"
        else "public_samples_standard"
    )
)
ALLOWED = {
    "api.exchange.coinbase.com": (
        "/products/BTC-USD",
        "/products/SOL-USD",
        "/products/BTC-USD/book",
        "/products/SOL-USD/book",
    ),
    "api.bybit.com": ("/v5/market/funding/history", "/v5/market/open-interest"),
    "www.okx.com": (
        "/api/v5/public/funding-rate-history",
        "/api/v5/public/open-interest",
        "/api/v5/rubik/stat/contracts/open-interest-history",
        "/api/v5/public/market-data-history",
    ),
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Redirect not followed", headers, fp)


LAST = None
BLOCKED = set()


def fetch(name, host, path, params=None):
    global LAST
    if host not in ALLOWED or path not in ALLOWED[host]:
        raise ValueError("Public endpoint not allowlisted")
    if host in BLOCKED:
        return
    url = "https://" + host + path + ("?" + urlencode(params) if params else "")
    if LAST is not None:
        time.sleep(max(0, 1.1 - (time.monotonic() - LAST)))
    started = time.time()
    mono = time.monotonic()
    gap = mono - LAST if LAST is not None else None
    LAST = mono
    request = Request(
        url, headers={"User-Agent": "BHABIT-public-research-prototype/1"}, method="GET"
    )
    status = None
    body = b""
    error = None
    try:
        with build_opener(NoRedirect()).open(request, timeout=25) as response:
            status = response.status
            body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ValueError("Response too large for sample")
    except HTTPError as exc:
        status = exc.code
        body = exc.read(100000)
        error = str(exc)
        if status in (403, 451, 429):
            BLOCKED.add(host)
    except (URLError, TimeoutError, ValueError) as exc:
        error = repr(exc)
    payload = None
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        pass
    if isinstance(payload, dict) and (
        str(payload.get("code")) == "50011" or payload.get("retCode") == 10006
    ):
        BLOCKED.add(host)
    record = {
        "name": name,
        "url": url,
        "method": "GET",
        "requested_at_utc": datetime.datetime.fromtimestamp(
            started, datetime.timezone.utc
        ).isoformat(),
        "request_start_gap_seconds": gap,
        "status": status,
        "error": error,
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "payload": payload,
        "non_json_prefix": (
            body[:200].decode("utf-8", "replace") if payload is None else None
        ),
    }
    with (OUT / (name + ".json")).open("x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
    row = {
        "sample": name,
        "file": str((OUT / (name + ".json")).resolve()),
        **{
            k: record[k]
            for k in (
                "url",
                "requested_at_utc",
                "request_start_gap_seconds",
                "status",
                "error",
                "body_sha256",
                "bytes",
            )
        },
    }
    if isinstance(payload, dict):
        rows = payload.get("data", payload.get("result", {}))
        if isinstance(rows, dict):
            rows = rows.get("list", [])
        row["response_code"] = payload.get("code", payload.get("retCode"))
        row["records"] = len(rows) if isinstance(rows, list) else None
        row["first_record"] = rows[0] if isinstance(rows, list) and rows else None
        if "bids" in payload:
            row["bid_levels"] = len(payload["bids"])
            row["ask_levels"] = len(payload.get("asks", []))
            row["best_bid"] = payload["bids"][:1]
            row["best_ask"] = payload.get("asks", [])[:1]
    with (OUT / "requests.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    print(json.dumps(row), flush=True)


def archive_sample(name, url, kind):
    global LAST
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "static.okx.com"
        or not parsed.path.startswith("/cdn/")
    ):
        raise ValueError("Only a returned public OKX CDN archive URL is allowed")
    if LAST is not None:
        time.sleep(max(0, 1.1 - (time.monotonic() - LAST)))
    gap = time.monotonic() - LAST if LAST is not None else None
    LAST = time.monotonic()
    req = Request(
        url,
        headers={
            "User-Agent": "BHABIT-public-research-prototype/1",
            "Range": "bytes=0-131071",
        },
        method="GET",
    )
    record = {
        "sample": name,
        "url": url,
        "range_requested": "bytes=0-131071",
        "request_start_gap_seconds": gap,
        "whole_archive_downloaded": False,
        "status": None,
        "sample_rows": [],
        "error": None,
    }
    try:
        with build_opener(NoRedirect()).open(req, timeout=25) as response:
            record["status"] = response.status
            record["content_range"] = response.headers.get("Content-Range")
            record["content_length"] = response.headers.get("Content-Length")
            payload = response.read(131072)
        record["downloaded_bytes"] = len(payload)
        record["downloaded_sha256"] = hashlib.sha256(payload).hexdigest()
        if kind == "tar.gz":
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r|gz") as archive:
                for member in archive:
                    if member.isfile():
                        stream = archive.extractfile(member)
                        record["member"] = member.name
                        for _ in range(4):
                            line = stream.readline(400000)
                            if not line:
                                break
                            record["sample_rows"].append(
                                line.decode("utf-8", "replace").rstrip()
                            )
                        break
        else:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                record["member"] = archive.namelist()[0]
                with archive.open(record["member"]) as stream:
                    for _ in range(4):
                        line = stream.readline(400000)
                        if not line:
                            break
                        record["sample_rows"].append(
                            line.decode("utf-8", "replace").rstrip()
                        )
                total = (
                    int(record["content_range"].rsplit("/", 1)[1])
                    if record.get("content_range")
                    else int(record["content_length"] or "-1")
                )
                record["whole_archive_downloaded"] = len(payload) == total
    except (
        HTTPError,
        URLError,
        TimeoutError,
        ValueError,
        tarfile.TarError,
        zipfile.BadZipFile,
        EOFError,
        OSError,
    ) as exc:
        record["error"] = repr(exc)
    with (OUT / (name + ".json")).open("x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
    print(
        json.dumps({k: v for k, v in record.items() if k != "sample_rows"}), flush=True
    )


def main():
    OUT.mkdir(exist_ok=False)
    now = int(time.time() * 1000)
    if MODE == "archive_samples":
        history = pathlib.Path(".runtime/redteam_20261018/public_samples_history")
        for source, kind, label in [
            ("okx_BTC_depth_archive_365d.json", "tar.gz", "okx_BTC_depth_2025_sample"),
            (
                "okx_BTC_funding_archive_2025oct.json",
                "zip",
                "okx_BTC_funding_2025_sample",
            ),
        ]:
            body = json.loads((history / source).read_text())["payload"]
            link = body["data"][0]["details"][0]["groupDetails"][-1]["url"]
            archive_sample(label, link, kind)
    elif MODE == "history":
        for days, period in ((59, "1H"), (61, "1H"), (90, "4H"), (365, "1Dutc")):
            end = now - days * 86400000
            start = end - 2 * 86400000
            fetch(
                f"okx_BTC_oi_{days}d_{period}",
                "www.okx.com",
                "/api/v5/rubik/stat/contracts/open-interest-history",
                {
                    "instId": "BTC-USDT-SWAP",
                    "period": period,
                    "begin": start,
                    "end": end,
                    "limit": 3,
                },
            )
        for days in (5, 365):
            end = now - days * 86400000
            start = end - 86400000
            fetch(
                f"okx_BTC_depth_archive_{days}d",
                "www.okx.com",
                "/api/v5/public/market-data-history",
                {
                    "module": "4",
                    "instType": "SPOT",
                    "instIdList": "BTC-USDT",
                    "dateAggrType": "daily",
                    "begin": start,
                    "end": end,
                },
            )
        # Monthly archived funding can differ from the rolling funding-history API.
        month = datetime.datetime(2025, 10, 1, tzinfo=datetime.timezone.utc)
        nextmonth = datetime.datetime(2025, 11, 1, tzinfo=datetime.timezone.utc)
        fetch(
            "okx_BTC_funding_archive_2025oct",
            "www.okx.com",
            "/api/v5/public/market-data-history",
            {
                "module": "3",
                "instType": "SWAP",
                "instFamilyList": "BTC-USDT",
                "dateAggrType": "monthly",
                "begin": int(month.timestamp() * 1000),
                "end": int(nextmonth.timestamp() * 1000) - 1,
            },
        )
    else:
        for coin in ("BTC", "SOL"):
            fetch(
                "coinbase_" + coin + "_listing",
                "api.exchange.coinbase.com",
                "/products/" + coin + "-USD",
            )
        for i in (1, 2):
            for coin in ("BTC", "SOL"):
                fetch(
                    f"coinbase_{coin}_depth_{i}",
                    "api.exchange.coinbase.com",
                    "/products/" + coin + "-USD/book",
                    {"level": 2},
                )
        for coin in ("BTC", "SOL"):
            fetch(
                "bybit_" + coin + "_funding_recent",
                "api.bybit.com",
                "/v5/market/funding/history",
                {"category": "linear", "symbol": coin + "USDT", "limit": 3},
            )
            fetch(
                "bybit_" + coin + "_oi_recent",
                "api.bybit.com",
                "/v5/market/open-interest",
                {
                    "category": "linear",
                    "symbol": coin + "USDT",
                    "intervalTime": "1h",
                    "limit": 3,
                },
            )
        # Bounded historical windows probe availability; they do not establish an earliest date.
        for days in (365, 90):
            end = now - days * 86400000
            start = end - 86400000
            fetch(
                f"bybit_BTC_oi_{days}d",
                "api.bybit.com",
                "/v5/market/open-interest",
                {
                    "category": "linear",
                    "symbol": "BTCUSDT",
                    "intervalTime": "1h",
                    "startTime": start,
                    "endTime": end,
                    "limit": 3,
                },
            )
        for coin in ("BTC", "SOL"):
            fetch(
                "okx_" + coin + "_funding_recent",
                "www.okx.com",
                "/api/v5/public/funding-rate-history",
                {"instId": coin + "-USDT-SWAP", "limit": 3},
            )
            fetch(
                "okx_" + coin + "_oi_current",
                "www.okx.com",
                "/api/v5/public/open-interest",
                {"instType": "SWAP", "instId": coin + "-USDT-SWAP"},
            )
            fetch(
                "okx_" + coin + "_oi_recent",
                "www.okx.com",
                "/api/v5/rubik/stat/contracts/open-interest-history",
                {"instId": coin + "-USDT-SWAP", "period": "1H", "limit": 3},
            )
        for days in (30, 90, 365):
            end = now - days * 86400000
            start = end - 86400000
            fetch(
                f"okx_BTC_oi_{days}d",
                "www.okx.com",
                "/api/v5/rubik/stat/contracts/open-interest-history",
                {
                    "instId": "BTC-USDT-SWAP",
                    "period": "1H",
                    "begin": start,
                    "end": end,
                    "limit": 3,
                },
            )
            fetch(
                f"okx_BTC_funding_{days}d",
                "www.okx.com",
                "/api/v5/public/funding-rate-history",
                {"instId": "BTC-USDT-SWAP", "before": start, "after": end, "limit": 3},
            )
    if LAST is not None and (OUT / "requests.jsonl").exists():
        rows = [
            json.loads(line)
            for line in (OUT / "requests.jsonl").read_text().splitlines()
        ]
        assert all(
            r["request_start_gap_seconds"] is None
            or r["request_start_gap_seconds"] >= 1
            for r in rows
        )
        print("Global <=1 request/second verified; blocked hosts were not retried.")


if __name__ == "__main__":
    main()
