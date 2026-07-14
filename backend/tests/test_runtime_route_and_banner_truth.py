from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as backend_app


def test_script_entrypoint_runs_after_coin_insights_route_registration():
    source = Path(backend_app.__file__).read_text(encoding="utf-8")

    route_position = source.index('@app.get("/api/insights/<path:symbol>")')
    start_position = source.rindex('if __name__ == "__main__":\n    main()')

    assert start_position > route_position


def test_mobile_bundle_does_not_invent_volume_change(monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_compute_top_banner_data_safe",
        lambda: [
            {
                "symbol": "BTC-USD",
                "current_price": 100_000,
                "price_change_1h": 1.5,
            }
        ],
    )
    monkeypatch.setattr(backend_app, "_get_gainers_table_1min_swr", lambda: {})
    monkeypatch.setattr(backend_app, "_get_gainers_table_3min_swr", lambda: {})
    monkeypatch.setattr(backend_app, "_get_losers_table_3min_swr", lambda: {})
    monkeypatch.setattr(backend_app, "_mw_get_component_snapshot", lambda _name: None)

    with backend_app.app.test_request_context("/api/mobile/bundle"):
        response = backend_app.api_mobile_bundle()

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["banner1h"][0]["changePct1h"] == 1.5
    assert payload["volume1h"] == []


def test_bottom_banner_reports_warming_without_placeholder_rows(monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "get_banner_1h_volume",
        lambda **_kwargs: ([], "2026-07-13T00:00:00Z"),
    )

    with backend_app.app.test_request_context("/api/component/bottom-banner-scroll"):
        response = backend_app.get_bottom_banner_scroll()

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"] == []
    assert payload["warming"] is True


def test_real_one_hour_rows_keep_base_symbol_and_canonical_product_id(monkeypatch):
    monkeypatch.setattr(
        backend_app,
        "_db_baseline_for_window",
        lambda _symbol, _now, _window: (1_000, 100.0, 3_600),
    )
    monkeypatch.setattr(backend_app, "_set_baseline_meta_1h", lambda **_kwargs: None)

    rows = backend_app.calculate_1hour_price_changes(
        {"BTC-USD": 110.0}, snapshot_ts_s=4_600
    )

    assert rows[0]["symbol"] == "BTC"
    assert rows[0]["product_id"] == "BTC-USD"


def test_top_banner_component_reuses_the_canonical_background_snapshot(monkeypatch):
    row = {
        "symbol": "BTC",
        "product_id": "BTC-USD",
        "current_price": 110.0,
        "price_change_1h": 10.0,
        "source": "coinbase_sqlite_1h",
    }
    monkeypatch.setattr(
        backend_app,
        "_mw_get_component_snapshot",
        lambda name: {"data": [row]} if name == "banner_1h_price" else None,
    )
    monkeypatch.setattr(
        backend_app,
        "calculate_1hour_price_changes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("snapshot should avoid a request-time recompute")
        ),
    )

    assert backend_app._compute_top_banner_data_safe() == [row]


def test_volume_snapshot_endpoint_reuses_the_canonical_background_snapshot(monkeypatch):
    row = {
        "symbol": "BTC",
        "product_id": "BTC-USD",
        "volume_1h_now": 200.0,
        "volume_1h_prev": 100.0,
        "volume_change_1h_pct": 100.0,
        "source": "volume1h_sqlite",
    }
    monkeypatch.setattr(
        backend_app,
        "get_banner_1h_volume",
        lambda **_kwargs: ([row], "2026-07-13T00:00:00Z"),
    )

    with backend_app.app.test_request_context("/api/snapshots/one-hour-volume"):
        response, status = backend_app.one_hour_volume()

    assert status == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["warming"] is False
    assert payload["data"][0]["volume_now"] == 200.0
    assert payload["data"][0]["volume_1h_ago"] == 100.0
