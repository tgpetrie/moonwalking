import os

# Ensure Talisman remains disabled during test collection/runs unless explicitly enabled
# This prevents flask_talisman from trying to access app.jinja_env on lightweight MockFlask
os.environ.setdefault('DISABLE_TALISMAN', '1')

import pytest


@pytest.fixture(autouse=True)
def _ensure_testing_flag(monkeypatch):
    # Make sure Flask apps created during tests see TESTING=True unless the test overrides it
    monkeypatch.setenv('FLASK_ENV', 'development')
    return True
