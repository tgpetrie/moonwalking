from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

for path in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import app as backend_app
except Exception:  # pragma: no cover - fallback import path
    from backend import app as backend_app


def test_get_banner_1h_volume_can_bypass_stale_snapshot(monkeypatch):
    stale_snapshot = {
        "component": "banner_1h_volume",
        "data": [
            {"product_id": "STALE-USD", "symbol": "STALE", "volume_change_1h_pct": 1.0}
        ],
        "last_updated": "2026-03-11T00:00:00Z",
    }
    fresh_rows = [
        {
            "product_id": "FRESH-USD",
            "symbol": "FRESH",
            "volume_1h_now": 120.0,
            "volume_1h_prev": 60.0,
            "volume_change_1h_pct": 100.0,
            "baseline_mode": "full",
            "baseline_minutes": 60,
        }
    ]

    monkeypatch.setattr(
        backend_app,
        "_mw_get_component_snapshot",
        lambda name: stale_snapshot if name == "banner_1h_volume" else None,
    )
    monkeypatch.setattr(
        backend_app,
        "_volume1h_build_payload_snapshot",
        lambda: {"gainers_1m": [], "gainers_3m": [], "losers_3m": []},
    )
    monkeypatch.setattr(
        backend_app, "_volume1h_compute_ranked", lambda payload: list(fresh_rows)
    )

    cached_rows, _ = backend_app.get_banner_1h_volume()
    rebuilt_rows, _ = backend_app.get_banner_1h_volume(prefer_snapshot=False)

    assert cached_rows[0]["product_id"] == "STALE-USD"
    assert rebuilt_rows[0]["product_id"] == "FRESH-USD"
