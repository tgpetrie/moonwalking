from pathlib import Path

from backend import price_db


def test_recent_price_snapshots_are_chronological_and_bounded(tmp_path, monkeypatch):
    db_path = Path(tmp_path) / "prices.sqlite"
    monkeypatch.setattr(price_db, "DB_PATH", str(db_path))
    price_db.ensure_price_db()

    for ts in (100, 108, 116, 124):
        price_db.insert_price_snapshot(ts, [("SKY-USD", ts / 1000)])

    assert price_db.get_recent_price_snapshots("SKY-USD", limit=3) == [
        (108, 0.108),
        (116, 0.116),
        (124, 0.124),
    ]
    assert price_db.get_recent_price_snapshots("SKY-USD", limit=10, since_ts=116) == [
        (116, 0.116),
        (124, 0.124),
    ]
