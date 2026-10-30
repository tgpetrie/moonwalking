"""Offline sparse receipt-time recorder. No socket, backend or account access."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3


VERSION = "instant-micro-replay-v1-draft"
GRID = 5000
CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/research/INSTANT_OFFLINE_REPLAY_CONTRACT_V1_DRAFT.json"
)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("nonnegative integer timestamp/sequence required")
    return value


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if math.isfinite(result) else None


class ReplayStore:
    def __init__(self, path, *, create=False):
        path = Path(path)
        self.writable = create
        raw = CONTRACT_PATH.read_text(encoding="utf-8").encode("utf-8")
        cfg = json.loads(raw)
        if (
            cfg["version"] != VERSION
            or cfg["grid_ms"] != GRID
            or cfg["max_quote_age_ms"] != 10000
        ):
            raise ValueError("replay contract and implementation differ")
        contract_hash = hashlib.sha256(raw).hexdigest()
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb"):
                pass
            self.db = sqlite3.connect(path)
            self.db.executescript(
                """
                CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT INTO meta VALUES('version','instant-micro-replay-v1-draft');
                INSERT INTO meta VALUES('status','incomplete');
                CREATE TABLE packets(seq INTEGER PRIMARY KEY, receipt INTEGER, mono INTEGER,
                    connection TEXT, product TEXT, kind TEXT, payload TEXT);
                CREATE TABLE quotes(seq INTEGER PRIMARY KEY, product TEXT, receipt INTEGER,
                    bid REAL, ask REAL, bid_size REAL, ask_size REAL);
                CREATE INDEX quote_time ON quotes(product,receipt);
                CREATE TABLE trades(product TEXT, trade_id INTEGER, receipt INTEGER,
                    price REAL, size REAL, side TEXT, usd REAL,
                    PRIMARY KEY(product,trade_id));
                CREATE INDEX trade_time ON trades(product,receipt);
                CREATE TABLE micro_bars_5s(product TEXT, start INTEGER,
                    PRIMARY KEY(product,start));
                CREATE TABLE health(product TEXT, start INTEGER, end INTEGER,
                    available INTEGER, verified INTEGER, evidence TEXT);
                CREATE TABLE issues(product TEXT, start INTEGER, end INTEGER,
                    available INTEGER, reason TEXT);
            """
            )
            self.db.execute(
                "INSERT INTO meta VALUES('contract_sha256',?)", (contract_hash,)
            )
            self.db.execute(
                "INSERT INTO meta VALUES('recorder_sha256',?)",
                (
                    hashlib.sha256(
                        Path(__file__).read_text(encoding="utf-8").encode("utf-8")
                    ).hexdigest(),
                ),
            )
            self.db.commit()
        else:
            self.db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        if (
            self.db.execute("SELECT value FROM meta WHERE key='version'").fetchone()[0]
            != VERSION
        ):
            self.db.close()
            raise ValueError("unsupported replay database")
        if (
            self.db.execute(
                "SELECT value FROM meta WHERE key='contract_sha256'"
            ).fetchone()[0]
            != contract_hash
        ):
            self.db.close()
            raise ValueError("replay database contract hash differs")

    def close(self):
        self.db.close()

    def _writeable(self):
        status = self.db.execute(
            "SELECT value FROM meta WHERE key='status'"
        ).fetchone()[0]
        if not self.writable or status != "incomplete":
            raise ValueError("replay store is sealed, failed or read-only")

    def _ready(self):
        if (
            self.db.execute("SELECT value FROM meta WHERE key='status'").fetchone()[0]
            != "complete"
        ):
            raise ValueError("only complete replay artifacts may be queried")

    def add_health(self, *, product, start, end, available, verified, evidence):
        self._writeable()
        start, end, available = map(integer, (start, end, available))
        if (
            not isinstance(product, str)
            or not product
            or not isinstance(evidence, str)
            or not evidence
            or end <= start
            or available < end
            or type(verified) is not bool
        ):
            raise ValueError(
                "health needs product, evidence, completed interval and known-at time"
            )
        self.db.execute(
            "INSERT INTO health VALUES(?,?,?,?,?,?)",
            (product, start, end, available, int(verified), evidence),
        )

    def ingest(self, envelope):
        self._writeable()
        try:
            self._ingest(envelope)
        except Exception:
            self.db.execute("UPDATE meta SET value='failed' WHERE key='status'")
            self.db.commit()
            raise

    def _ingest(self, envelope):
        seq, receipt = map(
            integer, (envelope["receipt_seq"], envelope["receipt_ts_ms"])
        )
        mono = envelope.get("receipt_monotonic_ns")
        if mono is not None:
            integer(mono)
        previous = self.db.execute(
            "SELECT seq,receipt,mono FROM packets ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if previous and (
            seq <= previous["seq"]
            or receipt < previous["receipt"]
            or (
                mono is not None
                and previous["mono"] is not None
                and mono < previous["mono"]
            )
        ):
            raise ValueError("receipt order or clock regressed; replay aborted")
        message = envelope["message"]
        kind, product = message.get("type"), message.get("product_id")
        payload = json.dumps(message, sort_keys=True, allow_nan=False)
        self.db.execute(
            "INSERT INTO packets VALUES(?,?,?,?,?,?,?)",
            (
                seq,
                receipt,
                mono,
                str(envelope.get("connection_id", "unknown")),
                product,
                kind,
                payload,
            ),
        )
        source = envelope.get("source", "ws")
        if source not in ("ws", "rest", "rest_recovery"):
            raise ValueError("unknown packet source")
        if source != "ws" or kind not in ("match", "ticker"):
            return  # REST recovery/last_match/heartbeats never become live executions.
        if not isinstance(product, str) or not product:
            raise ValueError("canonical product_id required")
        if kind == "ticker":
            self.db.execute(
                "INSERT INTO quotes VALUES(?,?,?,?,?,?,?)",
                (
                    seq,
                    product,
                    receipt,
                    number(message.get("best_bid")),
                    number(message.get("best_ask")),
                    number(message.get("best_bid_size")),
                    number(message.get("best_ask_size")),
                ),
            )
        else:
            trade_id = integer(message["trade_id"])
            price, size = number(message.get("price")), number(message.get("size"))
            if (
                price is None
                or size is None
                or min(price, size) <= 0
                or not math.isfinite(price * size)
            ):
                raise ValueError("invalid live match amount")
            side = (
                message.get("side") if message.get("side") in ("buy", "sell") else None
            )
            old = self.db.execute(
                "SELECT * FROM trades WHERE product=? AND trade_id=?",
                (product, trade_id),
            ).fetchone()
            if old:
                if (old["price"], old["size"], old["side"]) != (price, size, side):
                    self.db.execute(
                        "INSERT INTO issues VALUES(?,?,?,?,?)",
                        (
                            product,
                            old["receipt"] // GRID * GRID,
                            receipt // GRID * GRID + GRID,
                            receipt,
                            "conflicting_trade_id",
                        ),
                    )
                return
            self.db.execute(
                "INSERT INTO trades VALUES(?,?,?,?,?,?,?)",
                (product, trade_id, receipt, price, size, side, price * size),
            )
        self.db.execute(
            "INSERT OR IGNORE INTO micro_bars_5s VALUES(?,?)",
            (product, receipt // GRID * GRID),
        )

    def finalize(self, source_manifest=None):
        self._writeable()
        self.db.execute(
            "INSERT INTO meta VALUES('source_manifest',?)",
            (
                json.dumps(
                    source_manifest
                    or {"status": "caller_inputs_not_independently_verified"},
                    sort_keys=True,
                ),
            ),
        )
        self.db.execute("UPDATE meta SET value='complete' WHERE key='status'")
        self.db.commit()

    def coverage(self, product, start, end, asof):
        self._ready()
        for value in (start, end, asof):
            integer(value)
        if end <= start or asof < end:
            return False, None
        issue = self.db.execute(
            "SELECT available FROM issues WHERE product=? AND start<? AND end>? AND available<=? ORDER BY available DESC LIMIT 1",
            (product, end, start, asof),
        ).fetchone()
        if issue:
            return False, issue["available"]
        negative = self.db.execute(
            "SELECT available FROM health WHERE product=? AND start<? AND end>? AND available<=? AND verified=0 ORDER BY available DESC LIMIT 1",
            (product, end, start, asof),
        ).fetchone()
        if negative:
            return False, negative["available"]
        cursor, known = start, start
        spans = self.db.execute(
            "SELECT * FROM health WHERE product=? AND start<? AND end>? AND available<=? AND verified=1 ORDER BY start,end",
            (product, end, start, asof),
        )
        for span in spans:
            if span["end"] <= cursor:
                continue
            if span["start"] > cursor:
                return False, None
            cursor = span["end"]
            known = max(known, span["available"])
            if cursor >= end:
                return True, known
        return False, None

    def trades_window(self, product, start, end, *, asof):
        self._ready()
        for value in (start, end, asof):
            integer(value)
        if start >= end or asof < end:
            raise ValueError(
                "completed half-open window and causal knowledge cutoff required"
            )
        verified, known = self.coverage(product, start, end, asof)
        trades = list(
            self.db.execute(
                "SELECT * FROM trades WHERE product=? AND receipt>=? AND receipt<?",
                (product, start, end),
            )
        )
        # Match side names the maker; invert for taker participation.
        amounts = {
            side: sum(r["usd"] for r in trades if r["side"] == side)
            for side in ("buy", "sell", None)
        }
        return dict(
            coverage_verified=verified,
            available_ts_ms=max(end, known or end),
            observed_trade_count=len(trades),
            trade_count=len(trades) if verified else None,
            trade_count_at_window_start=(
                sum(r["receipt"] == start for r in trades) if verified else None
            ),
            quote_volume_usd=sum(amounts.values()) if verified else None,
            taker_buy_usd=amounts["sell"] if verified else None,
            taker_sell_usd=amounts["buy"] if verified else None,
            unknown_side_usd=amounts[None] if verified else None,
            flow_available=verified and amounts[None] == 0,
        )

    def snapshot(self, product, cutoff, *, asof=None):
        self._ready()
        integer(cutoff)
        asof = cutoff if asof is None else integer(asof)
        if cutoff % GRID or asof < cutoff:
            raise ValueError(
                "closed grid cutoff and knowledge as-of >= cutoff required"
            )
        start = cutoff - GRID
        window = self.trades_window(product, start, cutoff, asof=asof)
        quote = self.db.execute(
            "SELECT * FROM quotes WHERE product=? AND receipt<? ORDER BY receipt DESC,seq DESC LIMIT 1",
            (product, cutoff),
        ).fetchone()
        observed = list(
            self.db.execute(
                "SELECT * FROM quotes WHERE product=? AND receipt>=? AND receipt<? ORDER BY receipt,seq",
                (product, start, cutoff),
            )
        )
        valid = (
            lambda q: q["bid"] is not None
            and q["ask"] is not None
            and 0 < q["bid"] <= q["ask"]
        )
        reason = None
        quote_coverage, quote_known = (
            self.coverage(product, quote["receipt"], cutoff, asof)
            if quote
            else (False, None)
        )
        if not window["coverage_verified"]:
            reason = "unverified_coverage"
        elif quote is None:
            reason = "missing_quote"
        elif not valid(quote):
            reason = "invalid_quote"
        elif cutoff - quote["receipt"] > 10000:
            reason = "stale_quote"
        elif not quote_coverage:
            reason = "quote_crossed_unverified_interval"
        mids = [q["bid"] / 2 + q["ask"] / 2 for q in observed if valid(q)]
        sizes_valid = (
            quote is not None
            and all(
                quote[k] is not None and quote[k] >= 0 for k in ("bid_size", "ask_size")
            )
            and quote["bid_size"] + quote["ask_size"] > 0
        )
        window["available_ts_ms"] = max(
            window["available_ts_ms"], quote_known or cutoff
        )
        boundary_count = window.pop("trade_count_at_window_start")
        return dict(
            **window,
            product_id=product,
            ts_ms=cutoff,
            trade_count_at_bucket_start=boundary_count,
            knowledge_asof_ts_ms=asof,
            reason=reason,
            price_source="mid" if reason is None else "unavailable",
            mid=quote["bid"] / 2 + quote["ask"] / 2 if reason is None else None,
            quote_ts_ms=quote["receipt"] if quote else None,
            bid=quote["bid"] if quote else None,
            ask=quote["ask"] if quote else None,
            bid_size=quote["bid_size"] if quote else None,
            ask_size=quote["ask_size"] if quote else None,
            bbo_size_available=reason is None and sizes_valid,
            quote_observed=bool(observed),
            observed_mid_ohlc=(
                [mids[0], max(mids), min(mids), mids[-1]] if mids else None
            ),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "packets", type=Path, help="local receipt-ordered JSONL or JSONL.gz"
    )
    parser.add_argument(
        "--health",
        type=Path,
        required=True,
        help="explicit interval assertions with evidence and availability timestamps",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="new offline SQLite artifact; existing files refused",
    )
    args = parser.parse_args()
    input_hashes = dict(packets=digest(args.packets), health=digest(args.health))
    store = ReplayStore(args.out, create=True)
    try:
        opener = gzip.open if args.packets.suffix == ".gz" else open
        with opener(args.packets, "rt", encoding="utf-8") as source:
            for line in source:
                store.ingest(json.loads(line))
        for span in json.loads(args.health.read_text(encoding="utf-8")):
            store.add_health(**span)
        if input_hashes != dict(
            packets=digest(args.packets), health=digest(args.health)
        ):
            raise ValueError("input files changed while replaying")
        store.finalize(
            dict(
                input_sha256=input_hashes,
                recorder_sha256=hashlib.sha256(
                    Path(__file__).read_text(encoding="utf-8").encode("utf-8")
                ).hexdigest(),
                feed_gate_pass=False,
            )
        )
        print(
            json.dumps(
                dict(
                    version=VERSION,
                    status="complete",
                    occupied_buckets=store.db.execute(
                        "SELECT COUNT(*) FROM micro_bars_5s"
                    ).fetchone()[0],
                    feed_gate_pass=False,
                )
            )
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
