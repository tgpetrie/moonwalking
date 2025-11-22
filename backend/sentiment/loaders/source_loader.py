"""Utilities for loading sentiment source metadata from versioned JSON files."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

SOURCES_ROOT = Path(__file__).resolve().parent.parent / "sources"
CANONICAL_TIERS = {"tier1", "tier2", "tier3", "fringe"}
REQUIRED_FIELDS = {"name", "description", "weight"}
_CATALOG_CACHE: Dict[Path, "SourceCatalog"] = {}


class SentimentSourceLoaderError(RuntimeError):
    """Raised when the source catalog cannot be read."""


def _normalize_tier(value: str | None, *, context: str) -> str:
    tier = (value or "").strip().lower()
    if tier not in CANONICAL_TIERS:
        raise SentimentSourceLoaderError(
            f"Unknown tier '{value}' in {context}; must be one of {sorted(CANONICAL_TIERS)}."
        )
    return tier


def _clean_url(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().rstrip("/").lower()


def _validate_entry(entry: Dict, tier_hint: str, *, path: Path, seen_names, seen_urls):
    if not isinstance(entry, dict):
        raise SentimentSourceLoaderError(
            f"Expected objects inside 'sources' array in {path.name}, got {type(entry).__name__}."
        )

    missing = []
    if not (entry.get("name") or "").strip():
        missing.append("name")
    if not (entry.get("description") or "").strip():
        missing.append("description")
    if entry.get("weight") is None:
        missing.append("weight")
    if missing:
        raise SentimentSourceLoaderError(
            f"Missing required fields {missing} in {path.name} for entry {entry!r}."
        )

    name = str(entry.get("name")).strip()
    if name.lower() in seen_names:
        raise SentimentSourceLoaderError(
            f"Duplicate source title '{name}' detected in {path.name}."
        )
    seen_names.add(name.lower())

    tier = _normalize_tier(entry.get("tier") or tier_hint, context=path.name)

    endpoint = _clean_url(
        entry.get("endpoint")
        or entry.get("url")
        or entry.get("href")
    )
    if endpoint:
        if endpoint in seen_urls:
            raise SentimentSourceLoaderError(
                f"Duplicate source endpoint '{endpoint}' detected in {path.name}."
            )
        seen_urls.add(endpoint)

    try:
        weight = float(entry.get("weight"))
    except (TypeError, ValueError) as exc:
        raise SentimentSourceLoaderError(
            f"Weight must be numeric for '{name}' in {path.name}."
        ) from exc

    merged = {**entry, "tier": tier, "weight": weight}
    return merged


def load_source_catalog(base_path: str | Path | None = None) -> List[Dict]:
    """Return a merged list of all tier JSON files.

    Each file is optional; missing tiers simply yield zero results. Raises a
    helpful error if the root directory is absent so callers can surface the
    misconfiguration early.
    """

    root = Path(base_path) if base_path else SOURCES_ROOT
    if not root.exists():
        raise SentimentSourceLoaderError(
            f"Sentiment sources directory not found at {root}."
        )

    entries: List[Dict] = []
    seen_titles = set()
    seen_urls = set()

    for json_path in sorted(root.glob("*.json")):
        with json_path.open("r", encoding="utf-8") as handle:
            try:
                payload = json.load(handle)
            except json.JSONDecodeError as exc:
                raise SentimentSourceLoaderError(
                    f"Invalid JSON in {json_path}: {exc}"
                ) from exc

        if not isinstance(payload, dict):
            raise SentimentSourceLoaderError(
                f"Expected an object in {json_path}, got {type(payload).__name__}."
            )

        schema_version = payload.get("schema_version")
        if schema_version != 1:
            raise SentimentSourceLoaderError(
                f"Unsupported schema_version '{schema_version}' in {json_path}; expected 1."
            )

        tier_hint = payload.get("tier") or json_path.stem
        tier_hint = _normalize_tier(tier_hint, context=json_path.name)

        sources = payload.get("sources")
        if not isinstance(sources, list):
            raise SentimentSourceLoaderError(
                f"Expected 'sources' array in {json_path}, got {type(sources).__name__}."
            )

        for entry in sources:
            merged = _validate_entry(entry, tier_hint, path=json_path, seen_names=seen_titles, seen_urls=seen_urls)
            entries.append(merged)

    return entries


@dataclass
class SourceCatalog:
    entries: List[Dict]

    def summary(self) -> Dict[str, Dict[str, int] | int]:
        counts = summarize_source_counts(self.entries)
        return {"total": sum(counts.values()), "tiers": counts}

    def serialized(self) -> List[Dict]:
        # Return a shallow copy so callers can't mutate the cache.
        return [dict(entry) for entry in self.entries]


def load_sources(base_path: str | Path | None = None, *, force_reload: bool = False) -> SourceCatalog:
    """Read and validate the source catalog, caching the result per path."""
    root = Path(base_path) if base_path else SOURCES_ROOT
    cache_key = root.resolve()

    if not force_reload and cache_key in _CATALOG_CACHE:
        return _CATALOG_CACHE[cache_key]

    entries = load_source_catalog(root)
    catalog = SourceCatalog(entries)
    _CATALOG_CACHE[cache_key] = catalog
    return catalog


def summarize_source_counts(entries: Iterable[Dict]) -> Dict[str, int]:
    """Compute a tier count map suitable for source breakdown widgets."""

    counts = {"tier1": 0, "tier2": 0, "tier3": 0, "fringe": 0}
    for entry in entries:
        tier = _normalize_tier(entry.get("tier"), context="catalog entry")
        counts[tier] = counts.get(tier, 0) + 1
    return counts


__all__ = [
    "SourceCatalog",
    "load_source_catalog",
    "load_sources",
    "summarize_source_counts",
    "SentimentSourceLoaderError",
]
