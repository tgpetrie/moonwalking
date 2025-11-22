from collections import defaultdict, deque
from backend.fixtures.seed_volumes import load_dev_volume_fixture


def test_load_dev_volume_fixture():
    hist = defaultdict(lambda: deque(maxlen=180))
    # Seed two test symbols for 10 minutes each
    res = load_dev_volume_fixture(hist, symbols=["AAA-USD", "BBB-USD"], minutes=10, logger=None)
    assert res["seeded_symbols"] == 2
    assert res["points_each"] == 10
    assert len(hist["AAA-USD"]) == 10
    assert len(hist["BBB-USD"]) == 10
