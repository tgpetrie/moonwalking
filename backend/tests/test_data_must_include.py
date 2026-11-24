"""/data must not fail when every must-include product is already on a board."""

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


def test_data_survives_must_include_product_already_on_a_board(monkeypatch):
    # AMP is both the must-include staple and a live 1m gainer, so there is
    # nothing to add. That used to leave missing_must unset: /data answered
    # with empty boards and errors.fatal on every such poll.
    snapshots = {
        "updated_at": "2026-11-24T15:00:00+00:00",
        "gainers_1m": {
            "data": [
                {"symbol": "AMP", "product_id": "AMP-USD", "current_price": 0.0042},
                {"symbol": "SOL", "product_id": "SOL-USD", "current_price": 148.65},
            ],
            "last_updated": "2026-11-24T15:00:00+00:00",
        },
    }
    monkeypatch.setattr(backend_app, "_MW_MUST_INCLUDE_PRODUCTS", ["AMP-USD"])
    monkeypatch.setattr(
        backend_app, "_mw_get_component_snapshot", lambda name: snapshots.get(name)
    )

    response = backend_app.app.test_client().get("/data")

    assert response.status_code == 200
    payload = response.get_json()
    assert "fatal" not in (payload.get("errors") or {})
    assert {row["symbol"] for row in payload["gainers_1m"]} >= {"AMP", "SOL"}
    coverage = payload["coverage"]
    assert coverage["must_include_missing_before"] == []
    assert coverage["must_include_missing"] == []
    assert coverage["must_include_added"] == []
