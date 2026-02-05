"""
Minimal local stubs for pydantic-style schema models used by the backend.

These are purposely lightweight fallbacks to allow the dev server to start
for local visual checks when the real generated/packaged `pyd_schemas` module
is not present. They expose a minimal interface used by `app.py`:

- __init__(**kwargs) -> stores values
- model_dump() -> returns stored dict
- model_json_schema() -> returns a tiny JSON-schema-like dict

If you have the real `pyd_schemas` module (generated from pydantic models),
prefer to use that instead of these stubs.
"""

from typing import Any, Dict


class _BaseStub:
    def __init__(self, **kwargs: Any):
        # store passed fields; preserve nested structures
        self._data = dict(kwargs or {})

    def model_dump(self) -> Dict[str, Any]:
        return dict(self._data)

    @classmethod
    def model_json_schema(cls) -> Dict[str, Any]:
        # very small placeholder schema useful for OpenAPI responses
        return {
            "title": cls.__name__,
            "type": "object",
            "properties": {},
            "description": f"Fallback schema for {cls.__name__}",
        }


class HealthResponse(_BaseStub):
    """Represents a health check response payload."""


class MetricsResponse(_BaseStub):
    """Represents a metrics response payload."""


class Gainers1mComponent(_BaseStub):
    """Represents a component payload for the 1-minute gainers table."""


__all__ = ["HealthResponse", "MetricsResponse", "Gainers1mComponent"]
