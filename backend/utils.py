"""Backend utility placeholders.

This file previously contained a misfiled React component, which caused
Python import failures (e.g. NameError: undefined name) when
`backend/app.py` attempted `from utils import ...`.

Keep this module import-safe and lightweight.
"""

from __future__ import annotations

from typing import List, Dict, Any


def get_1h_volume_weighted_data() -> List[Dict[str, Any]]:
    """Optional helper hook for /api/snapshots/one-hour-volume.

    Return an empty list so callers can fall back safely.
    """
    return []
