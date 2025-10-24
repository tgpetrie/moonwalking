import os
import sys
import importlib.util
import pytest
import json

# Ensure backend package dir is on sys.path so relative imports inside app.py work
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

APP_PATH = os.path.join(ROOT, 'app.py')

spec = importlib.util.spec_from_file_location('backend_app', APP_PATH)
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)


@pytest.mark.parametrize("seed_env", ["1"])
def test_one_min_seed(monkeypatch, seed_env):
    """Verify seeded data is loaded correctly when USE_1MIN_SEED=1"""
    monkeypatch.setenv("USE_1MIN_SEED", seed_env)
    data = app_module.get_crypto_data_1min()
    assert isinstance(data, dict)
    assert "gainers" in data and len(data["gainers"]) > 0
    # Allow both explicit fixture marker OR a seeded cache entry
    assert data.get("source") in ("fixture-seed", "seeded") or app_module.one_minute_cache.get("data") is data


def test_fixture_file_exists():
    """Ensure the fixture JSON file exists and loads properly"""
    fixture_path = os.path.join(os.path.dirname(__file__), "../fixtures/top_movers_3m.json")
    assert os.path.exists(fixture_path)
    with open(fixture_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert "gainers" in data
    assert isinstance(data["gainers"], list)
