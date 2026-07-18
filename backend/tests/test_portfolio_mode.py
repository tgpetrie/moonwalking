from decimal import Decimal

import pytest
from flask import Flask

import backend.portfolio_mode as portfolio_module
from backend.portfolio_mode import (
    PageResult,
    PortfolioService,
    UnsafeCoinbasePermissions,
    reconstruct_cost_basis,
)


def _fill(*, side="BUY", size="1", price="100", commission="0", product_id="BTC-USD"):
    return {
        "side": side,
        "size": size,
        "price": price,
        "commission": commission,
        "product_id": product_id,
        "trade_time": "2026-07-18T00:00:00Z",
        "size_in_quote": False,
    }


def test_cost_basis_is_complete_when_fills_cover_current_quantity():
    basis = reconstruct_cost_basis(
        "BTC",
        Decimal("1.5"),
        [_fill(size="2", price="100", commission="2")],
    )

    assert basis["status"] == "complete"
    assert basis["known_quantity"] == 1.5
    assert basis["unknown_quantity"] == 0.0
    assert basis["average_price"] == 101.0
    assert basis["known_cost_usd"] == 151.5


def test_transferred_in_quantity_is_marked_partial_instead_of_invented():
    basis = reconstruct_cost_basis(
        "BTC",
        Decimal("2"),
        [_fill(size="0.5", price="100")],
    )

    assert basis["status"] == "partial"
    assert basis["known_quantity"] == 0.5
    assert basis["unknown_quantity"] == 1.5
    assert basis["known_cost_usd"] == 50.0


class FakeCoinbaseClient:
    def __init__(self, *, permissions=None):
        self.permissions = permissions or {
            "can_view": True,
            "can_trade": False,
            "can_transfer": False,
            "can_receive": False,
            "portfolio_uuid": "portfolio-1",
            "portfolio_type": "DEFAULT",
        }
        self.accounts_called = False

    def get_key_permissions(self):
        return self.permissions

    def list_accounts(self):
        self.accounts_called = True
        return PageResult(
            [
                {
                    "uuid": "btc-account",
                    "name": "BTC Wallet",
                    "currency": "BTC",
                    "active": True,
                    "ready": True,
                    "available_balance": {"value": "2"},
                    "hold": {"value": "0"},
                },
                {
                    "uuid": "usd-account",
                    "name": "USD Wallet",
                    "currency": "USD",
                    "active": True,
                    "ready": True,
                    "available_balance": {"value": "100"},
                    "hold": {"value": "0"},
                },
            ]
        )

    def list_fills(self):
        return PageResult([_fill(size="2", price="100", commission="2")])

    def list_orders(self):
        return PageResult(
            [
                {
                    "order_id": "order-1",
                    "product_id": "BTC-USD",
                    "side": "SELL",
                    "status": "OPEN",
                    "order_configuration": {
                        "limit_limit_gtc": {"base_size": "0.1", "limit_price": "180"}
                    },
                }
            ]
        )

    def get_product(self, product_id):
        assert product_id == "BTC-USD"
        return {"price": "150", "price_percentage_change_24h": "3.2"}


def test_service_refuses_trade_permission_before_loading_accounts():
    client = FakeCoinbaseClient(
        permissions={
            "can_view": True,
            "can_trade": True,
            "can_transfer": False,
            "portfolio_uuid": "portfolio-1",
        }
    )

    with pytest.raises(UnsafeCoinbasePermissions):
        PortfolioService(client).snapshot()

    assert client.accounts_called is False


def test_service_builds_view_only_summary_and_known_pnl():
    snapshot = PortfolioService(FakeCoinbaseClient()).snapshot()

    assert snapshot["mode"] == "view_only"
    assert snapshot["permissions"]["can_trade"] is False
    assert snapshot["summary"]["total_value_usd"] == 400.0
    assert snapshot["summary"]["cash_value_usd"] == 100.0
    assert snapshot["summary"]["known_unrealized_pnl_usd"] == 98.0
    assert snapshot["summary"]["cost_basis_coverage_pct"] == 100.0
    assert snapshot["summary"]["open_order_count"] == 1
    assert snapshot["holdings"][0]["symbol"] == "BTC"
    assert snapshot["holdings"][0]["cost_basis"]["status"] == "complete"


def _route_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="portfolio-test-secret",  # pragma: allowlist secret
    )
    app.register_blueprint(portfolio_module.portfolio_bp)
    return app


def test_portfolio_route_requires_authenticated_session(monkeypatch):
    monkeypatch.setattr(portfolio_module, "get_authenticated_user", lambda: None)
    response = _route_app().test_client().get("/api/portfolio")

    assert response.status_code == 401
    assert response.get_json()["status"] == "unauthorized"


def test_portfolio_route_is_owner_only(monkeypatch):
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(
        portfolio_module,
        "get_authenticated_user",
        lambda: {"id": 2, "email": "other@example.com"},
    )
    response = _route_app().test_client().get("/api/portfolio")

    assert response.status_code == 403
    assert response.get_json()["code"] == "portfolio_owner_only"
