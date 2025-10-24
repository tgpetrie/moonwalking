import os
import importlib.util
import json

import pytest

# Path to the backend app file
APP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app.py')


def setup_module(module):
    # Enable seeding via env for this module's tests
    os.environ['USE_1MIN_SEED'] = '1'

    # If running in CI, skip this test to avoid changing CI behavior
    if os.environ.get('CI'):
        import pytest as _pytest
        _pytest.skip('Skipping local seeding test in CI environment')


def teardown_module(module):
    os.environ.pop('USE_1MIN_SEED', None)


def _load_app_module():
    spec = importlib.util.spec_from_file_location('backend_app', APP_PATH)
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    # Ensure backend directory is importable so `import watchlist` and similar work
    backend_dir = os.path.dirname(APP_PATH)
    if backend_dir not in __import__('sys').path:
        __import__('sys').path.insert(0, backend_dir)
    loader.exec_module(mod)
    return mod


def test_get_crypto_data_1min_seeding(tmp_path, monkeypatch):
    # Load the backend module from file path to avoid package import issues
    app_mod = _load_app_module()

    # Simulate loading state: cache empty
    app_mod.one_minute_cache['data'] = None
    app_mod.one_minute_cache['timestamp'] = 0
    assert app_mod.one_minute_cache['data'] is None

    # Ensure fixtures dir points to a usable fixture; create one if repo doesn't have fixtures
    repo_root = os.path.dirname(app_mod.__file__)
    fixtures_dir = app_mod.CONFIG.get('FIXTURE_DIR', os.path.join(repo_root, 'fixtures'))
    if not os.path.exists(fixtures_dir):
        sample = {
            'gainers': [
                {'symbol': 'FOO', 'current': 1.0, 'pct_1m': 0.5},
                {'symbol': 'BAR', 'current': 2.0, 'pct_1m': 0.4},
                {'symbol': 'BAZ', 'current': 3.0, 'pct_1m': 0.3},
            ],
            'losers': [],
            'top24h': []
        }
        fpath = tmp_path / 'top_movers_3m.json'
        fpath.write_text(json.dumps(sample))
        monkeypatch.setitem(app_mod.CONFIG, 'FIXTURE_DIR', str(tmp_path))

    # Call the function under test
    data = app_mod.get_crypto_data_1min()

    assert data is not None, "Expected seeded data, got None"
    assert isinstance(data, dict)
    assert 'gainers' in data
    assert len(data['gainers']) > 0, "Expected at least one seeded gainer"
    # Source may be a direct fixture seed or derived from 3-min snapshots
    allowed_sources = {'fixture-seed', 'derived-from-3min'}
    assert data.get('source') in allowed_sources or data.get('seeded') is True

    # Also ensure the cache persisted the seeded payload
    cached = app_mod.one_minute_cache['data']
    assert cached is not None
    assert cached.get('source') in allowed_sources or cached.get('seeded') is True
