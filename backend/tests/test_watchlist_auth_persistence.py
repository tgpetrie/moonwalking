import os
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import watchlist as watchlist_module


def make_test_app(tmp_path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"  # pragma: allowlist secret
    watchlist_module._WATCHLIST_DB_PATH = tmp_path / "watchlists.sqlite"
    watchlist_module._ensure_watchlist_schema()
    app.register_blueprint(watchlist_module.watchlist_bp)
    return app


def test_authenticated_watchlist_item_persists_added_price(tmp_path):
    app = make_test_app(tmp_path)

    with app.test_client() as client:
        signup = client.post(
            "/api/auth/signup",
            json={
                "name": "Board User",
                "email": "board@example.com",
                "password": "password123",  # pragma: allowlist secret
            },
        )
        assert signup.status_code == 201
        payload = signup.get_json()
        watchlist_id = payload["watchlists"][0]["id"]

        create_item = client.post(
            f"/api/watchlists/{watchlist_id}/items",
            json={
                "itemKey": "BTC",
                "itemType": "Asset",
                "title": "BTC",
                "notes": "",
                "addedPrice": 101234.56,
            },
        )
        assert create_item.status_code == 201
        watchlist = create_item.get_json()["watchlist"]
        item = watchlist["items"][0]
        assert item["itemKey"] == "BTC"
        assert item["addedPrice"] == 101234.56
        assert item["addedAt"]

        session_payload = client.get("/api/auth/session")
        assert session_payload.status_code == 200
        auth_data = session_payload.get_json()
        assert auth_data["watchlists"][0]["items"][0]["addedPrice"] == 101234.56
