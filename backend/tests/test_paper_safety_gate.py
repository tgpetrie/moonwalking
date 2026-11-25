"""Stage 2 safety gate: nothing in the codebase can send an order to Coinbase.

These tests read the source rather than run it, so they fail the moment an
order route, an order preview, or a non-GET Coinbase request is added, whether
or not anything calls it yet. Building a Coinbase-shaped order payload locally
(the paper ticket previews do this) is allowed; sending one is not.
"""

import ast
from pathlib import Path
import re

import pytest

REPO = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = (REPO / "backend", REPO / "scripts")
# Coinbase endpoints that create, change or move anything. Read-only history
# lives under /orders/historical and stays allowed.
WRITE_ENDPOINT = re.compile(
    r"brokerage/orders(?!/historical)"
    r"|orders/preview"
    r"|brokerage/convert"
    r"|portfolios/move_funds"
    r"|brokerage/intx/allocate"
    r"|/withdrawals"
    r"|/transactions/send",
)
WRITE_METHODS = {"post", "put", "patch", "delete", "request"}
# The only non-GET request any module may send to a Coinbase host: the OAuth
# token exchange behind "Sign in with Coinbase". It cannot trade.
ALLOWED_COINBASE_WRITES = {"https://api.coinbase.com/oauth/token"}


def _python_sources():
    for root in SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            parts = set(path.relative_to(REPO).parts)
            if parts & {"tests", "node_modules", ".venv", "venv", "__pycache__"}:
                continue
            yield path


def _parse(path):
    try:
        return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except SyntaxError:  # pragma: no cover - a broken file fails its own tests
        return None


def _strings(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def _module_constants(tree):
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value.value
    return constants


def _literal_text(node, constants):
    """The string a URL argument is built from, as far as the source shows."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id, node.id)
    if isinstance(node, ast.JoinedStr):
        return "".join(_literal_text(part, constants) for part in node.values)
    if isinstance(node, ast.FormattedValue):
        return _literal_text(node.value, constants)
    if isinstance(node, ast.BinOp):
        return _literal_text(node.left, constants) + _literal_text(
            node.right, constants
        )
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _non_get_calls(tree):
    """Outbound request calls that are not GETs, with their URL argument."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        method = next(
            (
                k.value
                for k in node.keywords
                if k.arg == "method" and isinstance(k.value, ast.Constant)
            ),
            None,
        )
        if name in WRITE_METHODS and node.args:
            yield node.lineno, node.args[0]
        elif name == "Request" and isinstance(getattr(method, "value", None), str):
            if method.value.upper() != "GET" and node.args:
                yield node.lineno, node.args[0]


def test_no_source_names_a_coinbase_order_or_money_movement_endpoint():
    found = [
        f"{path.relative_to(REPO)}:{line}: {text}"
        for path in _python_sources()
        if (tree := _parse(path)) is not None
        for line, text in _strings(tree)
        if WRITE_ENDPOINT.search(text)
    ]
    assert found == []


def test_no_non_get_request_reaches_a_coinbase_host_except_oauth_sign_in():
    found = []
    for path in _python_sources():
        tree = _parse(path)
        if tree is None:
            continue
        constants = _module_constants(tree)
        for line, target in _non_get_calls(tree):
            text = _literal_text(target, constants)
            if "coinbase" in text.lower() and text not in ALLOWED_COINBASE_WRITES:
                found.append(f"{path.relative_to(REPO)}:{line}: {text}")
    assert found == []


def _class(tree, name):
    return next(
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == name
    )


def test_the_authenticated_coinbase_client_can_only_send_get_requests():
    tree = _parse(REPO / "backend" / "portfolio_mode.py")
    client = _class(tree, "CoinbaseAdvancedTradeClient")
    methods = {n.name for n in client.body if isinstance(n, ast.FunctionDef)}
    assert not methods & WRITE_METHODS
    http_calls = {
        node.func.attr
        for node in ast.walk(client)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "http"
    }
    assert http_calls == {"get"}
    signed = [
        node.args[0].value
        for node in ast.walk(client)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_jwt"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert signed and set(signed) == {"GET"}


def test_the_public_quote_paths_only_read():
    collector = _parse(REPO / "scripts" / "coinbase_paper_depth_collect.py")
    opens = [
        node
        for node in ast.walk(collector)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", getattr(node.func, "attr", ""))
        in ("urlopen", "opener")
    ]
    assert opens, "the collector should read the public book"
    for call in opens:
        assert len(call.args) == 1, "urlopen with a body would be a POST"
        assert not any(k.arg == "data" for k in call.keywords)
    context = _parse(REPO / "backend" / "agents" / "cycle_context.py")
    assert not [line for line, _ in _non_get_calls(context)]


@pytest.mark.parametrize(
    "snippet",
    [
        'requests.post("https://api.coinbase.com/api/v3/brokerage/orders", json={})',
        'URL = "https://api.coinbase.com/api/v3/brokerage/orders"\nsession.post(URL)',
        'session.post(f"{BASE}/api/v3/brokerage/orders/preview")',
        'Request("https://api.coinbase.com/api/v3/brokerage/orders", method="POST")',
        'self.http.post("https://api.exchange.coinbase.com/orders")',
    ],
)
def test_the_gate_itself_catches_an_order_route(snippet):
    tree = ast.parse(snippet)
    constants = _module_constants(tree)
    named = [text for _, text in _strings(tree) if WRITE_ENDPOINT.search(text)]
    sent = [
        _literal_text(target, constants)
        for _, target in _non_get_calls(tree)
        if "coinbase" in _literal_text(target, constants).lower()
        or WRITE_ENDPOINT.search(_literal_text(target, constants))
    ]
    assert named or sent
