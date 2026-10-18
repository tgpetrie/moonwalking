"""Export market research only; run remotely via SSH, with no production writes.

The stdout envelope contains gzip/base64 JSONL, so SSH/PowerShell text handling
cannot corrupt the transfer. Never exports accounts, keys, or portfolio data.
"""

import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import time


def export(directory):
    captured = int(time.time())
    buffer = io.BytesIO()
    counts = {}
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as compressed:

        def write(row):
            compressed.write((json.dumps(row, separators=(",", ":")) + "\n").encode())

        write({"kind": "manifest", "captured_ts": captured, "schema_version": 1})
        queries = [
            (
                "signal",
                "signal_outcomes.sqlite",
                """
                SELECT signal_id,event_id,product_id,primary_state,read_label,
                       direction,confidence,started_ts,start_price
                FROM signal_outcomes WHERE started_ts <= ?
            """,
            ),
            (
                "candle",
                "volume_1h.sqlite",
                """
                SELECT product_id,hour_ts,open,high,low,close,base_volume,
                       minute_coverage,source
                FROM volume_hour WHERE hour_ts + 3600 <= ?
            """,
            ),
        ]
        for kind, name, query in queries:
            path = (Path(directory) / name).resolve()
            db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                db.execute("PRAGMA query_only=ON")
                db.execute("BEGIN")
                counts[kind] = 0
                for row in db.execute(query, (captured,)):
                    write({"kind": kind, **dict(row)})
                    counts[kind] += 1
            finally:
                db.close()
        write({"kind": "counts", **counts})
    payload = buffer.getvalue()
    print("BHABIT_RESEARCH_BEGIN " + hashlib.sha256(payload).hexdigest())
    encoded = base64.b64encode(payload).decode("ascii")
    for i in range(0, len(encoded), 65536):
        print(encoded[i : i + 65536])
    print("BHABIT_RESEARCH_END")


def decode(envelope, output):
    lines = Path(envelope).read_text(encoding="utf-8-sig").splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.startswith("BHABIT_RESEARCH_BEGIN ")
    )
    end = lines.index("BHABIT_RESEARCH_END", start + 1)
    expected = lines[start].split()[1]
    payload = base64.b64decode("".join(lines[start + 1 : end]), validate=True)
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("Research export checksum mismatch")
    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as source:
        for _ in source:
            pass  # Verify the gzip CRC before saving.
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as handle:
        handle.write(payload)
    print(json.dumps({"path": str(destination.resolve()), "sha256": expected}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory")
    parser.add_argument("--decode")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.decode and args.output:
        decode(args.decode, args.output)
    elif args.directory and not args.decode:
        export(args.directory)
    else:
        parser.error("Use --directory, or --decode ENVELOPE --output NEW_FILE")
