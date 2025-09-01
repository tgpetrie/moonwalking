"""Shared JSON Schemas for API contract validation."""

DATA_SCHEMA = {
    "type": "object",
    "required": ["gainers", "losers", "top24h", "banner"],
    "properties": {
        "gainers": {"type": "array"},
        "losers": {"type": "array"},
        "top24h": {"type": "array"},
        "banner": {"type": "array"}
    }
}

SIGNALS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["symbol", "direction", "score", "ts"],
        "properties": {
            "symbol": {"type": "string"},
            "direction": {"type": "string"},
            "score": {"type": "number"},
            "ts": {"type": "number"}
        }
    }
}
