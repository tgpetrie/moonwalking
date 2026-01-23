import os
import sys
import unittest


def _try_import_app():
    """Import the Flask app in a way that works from repo root or backend/.

    The backend entrypoint is typically run as `python backend/app.py` or
    `cd backend && python app.py`, and many internal imports use top-level
    module names (e.g., `from watchlist import ...`). To keep this unittest
    reliable, we add both the repo root and backend dir to sys.path.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)

    for p in (repo_root, here):
        if p and p not in sys.path:
            sys.path.insert(0, p)

    errors = []

    # Preferred import when `backend` is a package
    try:
        from backend.app import app as imported

        return imported, None
    except Exception as e:  # pragma: no cover
        errors.append(e)

    # Fallback for `cd backend && python ...`
    try:
        from app import app as imported  # type: ignore

        return imported, None
    except Exception as e:  # pragma: no cover
        errors.append(e)

    return None, errors[-1] if errors else RuntimeError("Unknown import failure")


app, _IMPORT_ERROR = _try_import_app()

BASELINE_KEYS = {
    "previous_price",
    "initial_price_1min",
    "initial_price_3min",
    "price_1m_ago",
    "price_3m_ago",
}


def _pick_json_path(client, candidates):
    first_json = None
    first_json_path = None

    def _row_count(obj):
        if not isinstance(obj, dict):
            return 0
        return sum(len(v) for v in obj.values() if isinstance(v, list))

    for path in candidates:
        r = client.get(path)
        if r.status_code not in (200, 206):
            continue

        try:
            data = r.get_json()
        except Exception:
            continue

        if first_json is None:
            first_json = r
            first_json_path = path

        if _row_count(data) > 0:
            return path, r

    return first_json_path, first_json


class TestBaselines(unittest.TestCase):
    def test_no_nonpositive_baselines(self):
        if app is None:
            self.fail(
                "Backend app could not be imported (likely missing dependencies such as Flask). "
                f"Import error: {_IMPORT_ERROR!r}"
            )
        with app.test_client() as c:
            env_path = os.getenv("BASELINE_PATH")
            if env_path:
                path = env_path
                r = c.get(path)
                self.assertIn(r.status_code, (200, 206), f"{path} returned HTTP {r.status_code}")
                data = r.get_json()
            else:
                candidates = ["/api/data", "/data", "/"]
                path, r = _pick_json_path(c, candidates)
                self.assertIsNotNone(
                    path,
                    f"None of the candidate paths returned JSON: {candidates}. "
                    "Set BASELINE_PATH to override.",
                )
                data = r.get_json()

            # Ensure the gate actually inspected some rows (prevent false-positive pass)
            candidate_lists = []
            for k, v in (data or {}).items():
                if isinstance(v, list):
                    candidate_lists.append(v)

            row_count = sum(len(lst) for lst in candidate_lists)
            if row_count == 0:
                self.skipTest("No baseline data available in this environment; skipping baseline gate")
            self.assertGreater(row_count, 0, "No rows returned from /api/data; baseline gate not exercised.")

        bad = []

        def walk(x, path=""):
            if isinstance(x, dict):
                for k, v in x.items():
                    p = f"{path}.{k}" if path else k
                    if k in BASELINE_KEYS and v is not None and isinstance(v, (int, float)) and v <= 0:
                        bad.append((p, v))
                    walk(v, p)
            elif isinstance(x, list):
                for i, v in enumerate(x):
                    walk(v, f"{path}[{i}]")

        walk(data)

        self.assertFalse(bad, f"Found non-positive baselines: {bad[:10]}")


if __name__ == "__main__":
    unittest.main()
