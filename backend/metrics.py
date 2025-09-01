"""Metrics exposition helpers for JSON and Prometheus outputs.

Separated to shrink app.py and reduce merge conflict surface.
"""
from __future__ import annotations
import time
from typing import Any, Dict, Iterable, Tuple, Callable

def collect_swr_cache_stats(now: float, entries: Iterable[Tuple[str, Callable, float, float]]):
    out = {}
    for name, fn, ttl, stale in entries:
        if not fn or not hasattr(fn, '_swr_cache_ts'):
            continue
        ts = getattr(fn, '_swr_cache_ts', 0.0) or 0.0
        base = {
            'cache_age_seconds': round(now - ts, 3) if ts else None,
            'served_cached_last': getattr(fn, '_swr_last_served_cached', False),
            'ttl': ttl,
            'stale_window': stale
        }
        stats = getattr(fn, '_swr_stats', None)
        if stats:
            base.update(stats)
        out[name] = base
    return out

def emit_prometheus(lines: list[str], name: str, value: Any, mtype: str, help_text: str):
    lines.append(f'# HELP {name} {help_text}')
    lines.append(f'# TYPE {name} {mtype}')
    if value is None:
        value = 'NaN'
    lines.append(f'{name} {value}')

def emit_swr_prometheus(lines: list[str], entries: Iterable[Tuple[str, Callable, float, float]]):
    now = time.time()
    for name, fn, ttl, stale in entries:
        if not fn or not hasattr(fn, '_swr_cache_ts'):
            continue
        ts = getattr(fn, '_swr_cache_ts', 0.0) or 0.0
        age = (now - ts) if ts else None
        stats = getattr(fn, '_swr_stats', {}) or {}
        emit_prometheus(lines, f'swr_{name}_cache_age_seconds', round(age,3) if age is not None else None, 'gauge', f'Age in seconds of SWR cache for {name}')
        emit_prometheus(lines, f'swr_{name}_ttl_seconds', ttl, 'gauge', f'TTL (fresh window) for {name}')
        emit_prometheus(lines, f'swr_{name}_stale_window_seconds', stale, 'gauge', f'Stale window for {name}')
        emit_prometheus(lines, f'swr_{name}_last_refresh_duration_seconds', stats.get('last_refresh_duration_sec'), 'gauge', f'Last refresh duration seconds for {name}')
        emit_prometheus(lines, f'swr_{name}_calls_total', stats.get('total_calls',0), 'counter', f'Total calls served for {name}')
        emit_prometheus(lines, f'swr_{name}_served_cached_total', stats.get('served_cached',0), 'counter', f'Served cached responses for {name}')
        emit_prometheus(lines, f'swr_{name}_served_fresh_total', stats.get('served_fresh',0), 'counter', f'Served fresh recomputations for {name}')
        emit_prometheus(lines, f'swr_{name}_background_refreshes_total', stats.get('background_refreshes',0), 'counter', f'Background refresh threads spawned for {name}')
