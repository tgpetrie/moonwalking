from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_COIN_LIST_TTL_S = 24 * 60 * 60
_ENDPOINT_TTL_S = 300
_SOCIAL_TTL_S = 120
_HTTP_TIMEOUT_S = 6

_COIN_LIST_URL = "https://api.coinpaprika.com/v1/coins"
_EVENTS_URL = "https://api.coinpaprika.com/v1/coins/{coin_id}/events"
_TWITTER_URL = "https://api.coinpaprika.com/v1/coins/{coin_id}/twitter"
_LUNARCRUSH_URL = "https://api.lunarcrush.com/v2"
_COINGECKO_SEARCH_URL = "https://api.coingecko.com/api/v3/search?query={query}"
_COINGECKO_COIN_URL = (
    "https://api.coingecko.com/api/v3/coins/{coin_id}"
    "?localization=false&tickers=false&market_data=false"
    "&community_data=true&developer_data=false&sparkline=false"
)

_CACHE_LOCK = threading.Lock()
_COIN_LIST_CACHE: dict[str, Any] = {
    "ts": 0.0,
    "items": [],
    "by_symbol": {},
}
_ENDPOINT_CACHE: dict[str, dict[str, Any]] = {}

_POSITIVE_WORDS = {
    "bull",
    "bullish",
    "breakout",
    "moon",
    "moonshot",
    "pump",
    "long",
    "uptrend",
    "squeeze",
    "rally",
    "accumulate",
    "rebound",
}

_NEGATIVE_WORDS = {
    "bear",
    "bearish",
    "dump",
    "crash",
    "short",
    "downtrend",
    "selloff",
    "rug",
    "fakeout",
    "reversal",
    "exhaustion",
    "capitulation",
}


def _now_s() -> float:
    return time.time()


def _now_ts() -> int:
    return int(_now_s())


def _normalize_symbol(symbol: str | None) -> str:
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    if "-" in raw:
        raw = raw.split("-", 1)[0]
    if raw.endswith("USD") and len(raw) > 3:
        raw = raw[:-3]
    return "".join(ch for ch in raw if ch.isalnum())


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except Exception:
        return None
    if math.isfinite(n):
        return n
    return None


def _to_int(value: Any) -> int | None:
    n = _to_float(value)
    if n is None:
        return None
    return int(round(n))


def _clamp(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _normalize_ts_s(value: Any) -> float | None:
    if value is None or value == "":
        return None

    n = _to_float(value)
    if n is not None:
        if n <= 0:
            return None
        if n > 1e12:
            n = n / 1000.0
        return n

    raw = str(value).strip()
    if not raw:
        return None

    iso_raw = raw
    if iso_raw.endswith("Z"):
        iso_raw = f"{iso_raw[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(iso_raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            continue

    return None


def _sentiment_label_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.2:
        return "Bullish"
    if score <= -0.2:
        return "Bearish"
    return "Mixed"


def _coerce_sentiment_payload(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        label_raw = str(value.get("label") or value.get("sentiment") or "").strip()
        net = _to_float(value.get("net_score"))
        if net is None:
            net = _to_float(value.get("netScore"))
        if net is None:
            net = _to_float(value.get("score"))
        if net is None:
            net = _to_float(value.get("value"))
        bullish = _to_float(value.get("bullish_pct"))
        if bullish is None:
            bullish = _to_float(value.get("bullishPct"))
        bearish = _to_float(value.get("bearish_pct"))
        if bearish is None:
            bearish = _to_float(value.get("bearishPct"))

        if bullish is None and bearish is not None:
            bullish = 100.0 - bearish
        if bearish is None and bullish is not None:
            bearish = 100.0 - bullish

        if net is None and bullish is not None and bearish is not None:
            total = bullish + bearish
            if total > 0:
                net = (bullish - bearish) / total

        if net is not None:
            net = _clamp(net, -1.0, 1.0)
        label = label_raw or _sentiment_label_from_score(net)
        if not label and net is None and bullish is None and bearish is None:
            return None

        if bullish is None and net is not None:
            bullish = _clamp((net + 1.0) * 50.0, 0.0, 100.0)
        if bearish is None and bullish is not None:
            bearish = _clamp(100.0 - bullish, 0.0, 100.0)

        return {
            "label": label or "Mixed",
            "net_score": round(net, 3) if net is not None else None,
            "bullish_pct": round(bullish, 1) if bullish is not None else None,
            "bearish_pct": round(bearish, 1) if bearish is not None else None,
        }

    n = _to_float(value)
    if n is not None:
        if abs(n) > 1.0:
            if 0.0 <= n <= 100.0:
                n = (n - 50.0) / 50.0
            elif -100.0 <= n <= 100.0:
                n = n / 100.0
            else:
                n = _clamp(n / 100.0, -1.0, 1.0)
        else:
            n = _clamp(n, -1.0, 1.0)
        label = _sentiment_label_from_score(n) or "Mixed"
        bullish = _clamp((n + 1.0) * 50.0, 0.0, 100.0)
        return {
            "label": label,
            "net_score": round(n, 3),
            "bullish_pct": round(bullish, 1),
            "bearish_pct": round(100.0 - bullish, 1),
        }

    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if raw in {"very_bullish", "bullish", "positive"}:
        return {
            "label": "Bullish",
            "net_score": 0.6,
            "bullish_pct": 80.0,
            "bearish_pct": 20.0,
        }
    if raw in {"very_bearish", "bearish", "negative"}:
        return {
            "label": "Bearish",
            "net_score": -0.6,
            "bullish_pct": 20.0,
            "bearish_pct": 80.0,
        }
    if raw in {"neutral", "mixed"}:
        return {
            "label": "Mixed",
            "net_score": 0.0,
            "bullish_pct": 50.0,
            "bearish_pct": 50.0,
        }
    return {
        "label": raw.title(),
        "net_score": None,
        "bullish_pct": None,
        "bearish_pct": None,
    }


def _sentiment_from_text(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    positive_hits = 0
    negative_hits = 0
    saw_text = False
    for item in items:
        text = str(item.get("text") or "").lower()
        if not text:
            continue
        saw_text = True
        tokens = [tok for tok in re.split(r"[^a-z]+", text) if tok]
        if not tokens:
            continue
        pos = sum(1 for tok in tokens if tok in _POSITIVE_WORDS)
        neg = sum(1 for tok in tokens if tok in _NEGATIVE_WORDS)
        positive_hits += pos
        negative_hits += neg

    total = positive_hits + negative_hits
    if not saw_text:
        return None
    if total <= 0:
        return {
            "label": "Mixed",
            "net_score": 0.0,
            "bullish_pct": 50.0,
            "bearish_pct": 50.0,
        }

    bullish_pct = (positive_hits / total) * 100.0
    bearish_pct = (negative_hits / total) * 100.0
    net = (positive_hits - negative_hits) / total
    label = _sentiment_label_from_score(net) or "Mixed"
    return {
        "label": label,
        "net_score": round(net, 3),
        "bullish_pct": round(bullish_pct, 1),
        "bearish_pct": round(bearish_pct, 1),
    }


def _empty_social_metrics(source: str = "none") -> dict[str, Any]:
    return {
        "social_volume_24h": None,
        "social_engagement_24h": None,
        "social_dominance_24h": None,
        "sentiment_24h": None,
        "social_rank": None,
        "social_heat": None,
        "social_heat_trend": None,
        "posts_60m": None,
        "posts_24h": None,
        "unique_authors_24h": None,
        "source": source,
        "updated_at": None,
    }


def _is_meaningful_metric(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return abs(float(value)) > 0.0
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_is_meaningful_metric(v) for v in value.values())
    return True


def _coin_rank(coin: dict[str, Any]) -> tuple[int, int, str]:
    is_active = bool(coin.get("is_active", True))
    raw_rank = coin.get("rank")
    try:
        rank = int(raw_rank)
    except Exception:
        rank = 999_999
    if rank <= 0:
        rank = 999_999
    coin_id = str(coin.get("id") or "")
    return (0 if is_active else 1, rank, coin_id)


def _build_symbol_index(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for coin in items:
        if not isinstance(coin, dict):
            continue
        sym = _normalize_symbol(coin.get("symbol"))
        if not sym:
            continue
        by_symbol.setdefault(sym, []).append(coin)

    for sym in list(by_symbol.keys()):
        by_symbol[sym].sort(key=_coin_rank)

    return by_symbol


def _http_get_json(url: str) -> tuple[int | None, Any, str | None]:
    req = Request(url, headers={"User-Agent": "moonwalkings/coin-intel"})
    try:
        with urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read().decode("utf-8", errors="replace")
            return int(status), json.loads(body or "null"), None
    except HTTPError as exc:
        status = getattr(exc, "code", None)
        try:
            body = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(body or "null")
        except Exception:
            parsed = None
        return status, parsed, f"http_error:{status}"
    except URLError as exc:
        return None, None, f"url_error:{exc}"
    except Exception as exc:
        return None, None, f"error:{exc}"


def _get_coin_list() -> tuple[list[dict[str, Any]], bool]:
    with _CACHE_LOCK:
        age = _now_s() - float(_COIN_LIST_CACHE.get("ts") or 0.0)
        cached_items = list(_COIN_LIST_CACHE.get("items") or [])
        if cached_items and age < _COIN_LIST_TTL_S:
            return cached_items, False

    status, data, err = _http_get_json(_COIN_LIST_URL)
    if status == 200 and isinstance(data, list):
        items = [item for item in data if isinstance(item, dict)]
        by_symbol = _build_symbol_index(items)
        with _CACHE_LOCK:
            _COIN_LIST_CACHE["ts"] = _now_s()
            _COIN_LIST_CACHE["items"] = items
            _COIN_LIST_CACHE["by_symbol"] = by_symbol
        return items, False

    with _CACHE_LOCK:
        cached_items = list(_COIN_LIST_CACHE.get("items") or [])
        if cached_items:
            return cached_items, True

    if err:
        logger.debug("coin intel: coin list unavailable (%s)", err)
    return [], True


def coinpaprika_coin_id(symbol: str | None) -> str | None:
    sym = _normalize_symbol(symbol)
    if not sym:
        return None

    items, _stale = _get_coin_list()
    if not items:
        return None

    with _CACHE_LOCK:
        by_symbol = _COIN_LIST_CACHE.get("by_symbol")
        if not isinstance(by_symbol, dict) or not by_symbol:
            by_symbol = _build_symbol_index(items)
            _COIN_LIST_CACHE["by_symbol"] = by_symbol

    candidates = list(by_symbol.get(sym) or [])
    if not candidates:
        return None

    best = candidates[0]
    cid = str(best.get("id") or "").strip()
    return cid or None


def _coingecko_coin_rank(coin: dict[str, Any]) -> tuple[int, str]:
    rank = _to_int(coin.get("market_cap_rank"))
    if rank is None or rank <= 0:
        rank = 999_999
    name = str(coin.get("name") or "")
    return (rank, name)


def coingecko_coin_id(symbol: str | None) -> str | None:
    sym = _normalize_symbol(symbol)
    if not sym:
        return None

    cache_key = f"coingecko:id:{sym}"
    cached = _cache_get(cache_key)
    if cached and isinstance(cached.get("payload"), dict):
        age = _now_s() - float(cached.get("ts") or 0.0)
        payload = dict(cached.get("payload") or {})
        cached_id = str(payload.get("coin_id") or "").strip()
        if cached_id and age < _COIN_LIST_TTL_S:
            return cached_id

    url = _COINGECKO_SEARCH_URL.format(query=quote(sym, safe=""))
    status, data, _err = _http_get_json(url)
    if status == 200 and isinstance(data, dict):
        raw_coins = data.get("coins")
        coins = [row for row in (raw_coins or []) if isinstance(row, dict)]
        exact = [row for row in coins if _normalize_symbol(row.get("symbol")) == sym]
        candidates = exact if exact else coins
        candidates.sort(key=_coingecko_coin_rank)
        if candidates:
            coin_id = str(candidates[0].get("id") or "").strip()
            if coin_id:
                _cache_set(
                    cache_key, {"coin_id": coin_id, "symbol": sym, "ts": _now_ts()}
                )
                return coin_id

    if cached and isinstance(cached.get("payload"), dict):
        cached_id = str((cached.get("payload") or {}).get("coin_id") or "").strip()
        if cached_id:
            return cached_id
    return None


def _cache_get(key: str) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        entry = _ENDPOINT_CACHE.get(key)
        if not isinstance(entry, dict):
            return None
        return dict(entry)


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _ENDPOINT_CACHE[key] = {
            "ts": _now_s(),
            "payload": payload,
        }


def _normalize_events(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        title = str(row.get("name") or row.get("title") or "").strip()
        if not title:
            continue
        item = {
            "id": str(row.get("id") or row.get("date_event") or title),
            "title": title,
            "when": row.get("date")
            or row.get("date_event")
            or row.get("created_at")
            or None,
            "description": str(row.get("description") or "").strip()[:300] or None,
            "source_url": row.get("link") or row.get("proof_image_link") or None,
        }
        out.append(item)
        if len(out) >= 10:
            break
    return out


def _normalize_social(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        text = str(row.get("status") or row.get("text") or "").strip()
        if not text:
            continue
        engagement = 0
        for key in (
            "engagement",
            "engagements",
            "interactions",
            "interaction_count",
            "retweets",
            "retweet_count",
            "likes",
            "likes_count",
            "favorite_count",
            "favorites",
            "reply_count",
            "replies_count",
            "quote_count",
        ):
            val = _to_int(row.get(key))
            if val and val > 0:
                engagement += val
        sentiment = _coerce_sentiment_payload(
            row.get("sentiment")
            or row.get("sentiment_score")
            or row.get("sentiment_label")
        )
        item = {
            "id": str(
                row.get("id") or row.get("status_id") or row.get("date") or text[:24]
            ),
            "text": text[:280],
            "author": row.get("user_name") or row.get("user") or None,
            "when": row.get("date") or row.get("created_at") or None,
            "source_url": row.get("status_link") or row.get("url") or None,
            "engagement": engagement if engagement > 0 else None,
            "sentiment": sentiment,
        }
        out.append(item)
        if len(out) >= 20:
            break
    return out


def _aggregate_status(*statuses: str | None) -> str:
    normalized = [
        str(s or "").strip().lower() for s in statuses if str(s or "").strip()
    ]
    if not normalized:
        return "offline"
    if any(s == "degraded" for s in normalized):
        return "degraded"
    if all(s == "live" for s in normalized):
        return "live"
    if any(s in {"live", "stale"} for s in normalized):
        return "stale"
    return "offline"


def _fetch_with_cache(
    *,
    key: str,
    url: str,
    normalize,
    ttl_s: int | None = None,
) -> dict[str, Any]:
    cached = _cache_get(key)
    effective_ttl = int(ttl_s or _ENDPOINT_TTL_S)
    if cached:
        age = _now_s() - float(cached.get("ts") or 0.0)
        payload = cached.get("payload") or {}
        if age < effective_ttl and isinstance(payload, dict):
            return {**payload, "status": "live"}

    status, data, err = _http_get_json(url)
    if status == 200:
        payload = {
            "status": "live",
            "items": normalize(data),
            "ts": _now_ts(),
        }
        _cache_set(key, payload)
        return payload

    if cached and isinstance(cached.get("payload"), dict):
        payload = dict(cached.get("payload") or {})
        payload["status"] = "stale"
        payload["ts"] = _now_ts()
        if err:
            payload["error"] = err
        return payload

    payload = {
        "status": "offline",
        "items": [],
        "ts": _now_ts(),
    }
    if err:
        payload["error"] = err
    if status == 429:
        payload["error"] = "rate_limited"
    return payload


def fetch_coinpaprika_events(coin_id: str | None) -> dict[str, Any]:
    cid = str(coin_id or "").strip()
    if not cid:
        return {
            "status": "offline",
            "items": [],
            "ts": _now_ts(),
            "error": "coin_id_missing",
        }
    key = f"events:{cid}"
    url = _EVENTS_URL.format(coin_id=quote(cid, safe=""))
    return _fetch_with_cache(key=key, url=url, normalize=_normalize_events)


def fetch_coinpaprika_twitter(coin_id: str | None) -> dict[str, Any]:
    cid = str(coin_id or "").strip()
    if not cid:
        return {
            "status": "offline",
            "items": [],
            "ts": _now_ts(),
            "error": "coin_id_missing",
        }
    key = f"twitter:{cid}"
    url = _TWITTER_URL.format(coin_id=quote(cid, safe=""))
    return _fetch_with_cache(
        key=key, url=url, normalize=_normalize_social, ttl_s=_SOCIAL_TTL_S
    )


def _derive_coinpaprika_metrics(
    symbol: str, social_feed: dict[str, Any]
) -> dict[str, Any]:
    items = list(social_feed.get("items") or [])
    now_s = _now_s()

    posts_24h = 0
    posts_60m = 0
    unique_authors: set[str] = set()
    engagement_24h = 0
    sentiment_items: list[dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        ts_s = _normalize_ts_s(item.get("when"))
        in_24h = True if ts_s is None else (now_s - ts_s) <= 24 * 60 * 60
        in_60m = False if ts_s is None else (now_s - ts_s) <= 60 * 60

        if in_24h:
            posts_24h += 1
            sentiment_items.append(item)
            author = str(item.get("author") or "").strip().lower()
            if author:
                unique_authors.add(author)
            engagement_val = _to_int(item.get("engagement"))
            if engagement_val and engagement_val > 0:
                engagement_24h += engagement_val
        if in_60m:
            posts_60m += 1

    sentiment_payload = _sentiment_from_text(sentiment_items)
    sentiment_payload = _coerce_sentiment_payload(sentiment_payload)

    social_dominance = None
    if posts_24h > 0:
        social_dominance = round(_clamp((posts_24h / 500.0) * 100.0, 0.0, 100.0), 2)

    social_heat = None
    heat_trend = None
    if posts_24h > 0 or engagement_24h > 0:
        volume_score = _clamp((posts_24h / 120.0) * 100.0, 0.0, 100.0)
        engagement_score = 0.0
        if engagement_24h > 0:
            engagement_score = _clamp(
                (math.log1p(float(engagement_24h)) / math.log1p(2500.0)) * 100.0,
                0.0,
                100.0,
            )
        velocity_score = 0.0
        if posts_24h > 0:
            expected_hourly = max(1.0, posts_24h / 24.0)
            ratio = posts_60m / expected_hourly
            velocity_score = _clamp((ratio / 2.0) * 100.0, 0.0, 100.0)
            if ratio >= 1.5:
                heat_trend = "rising"
            elif ratio <= 0.6:
                heat_trend = "collapsing"
            else:
                heat_trend = "flat"

        sentiment_boost = 0.0
        net_score = _to_float(
            sentiment_payload.get("net_score")
            if isinstance(sentiment_payload, dict)
            else None
        )
        if net_score is not None:
            sentiment_boost = net_score * 15.0
        social_heat = int(
            round(
                _clamp(
                    (0.45 * volume_score)
                    + (0.35 * engagement_score)
                    + (0.2 * velocity_score)
                    + sentiment_boost,
                    0.0,
                    100.0,
                )
            )
        )

    feed_status = str(social_feed.get("status") or "offline").strip().lower()
    if feed_status == "stale":
        status = "stale"
    elif feed_status in {"live", "degraded"}:
        status = "live"
    else:
        status = "offline"

    metrics = _empty_social_metrics(source="coinpaprika")
    metrics.update(
        {
            "social_volume_24h": posts_24h if posts_24h > 0 else None,
            "social_engagement_24h": engagement_24h if engagement_24h > 0 else None,
            "social_dominance_24h": social_dominance,
            "sentiment_24h": sentiment_payload,
            "social_rank": None,
            "social_heat": social_heat,
            "social_heat_trend": heat_trend,
            "posts_60m": posts_60m if posts_60m > 0 else None,
            "posts_24h": posts_24h if posts_24h > 0 else None,
            "unique_authors_24h": len(unique_authors) if unique_authors else None,
            "source": "coinpaprika",
            "updated_at": _now_ts(),
        }
    )

    return {
        "status": status,
        "metrics": metrics,
        "ts": _now_ts(),
    }


def _normalize_coingecko_metrics(
    asset: dict[str, Any], symbol: str, coin_id: str
) -> dict[str, Any] | None:
    community = (
        asset.get("community_data")
        if isinstance(asset.get("community_data"), dict)
        else {}
    )

    twitter_followers = _to_int(community.get("twitter_followers"))
    reddit_subscribers = _to_int(community.get("reddit_subscribers"))
    reddit_active_48h = _to_float(community.get("reddit_accounts_active_48h"))
    reddit_posts_48h = _to_float(community.get("reddit_average_posts_48h"))
    reddit_comments_48h = _to_float(community.get("reddit_average_comments_48h"))
    telegram_users = _to_int(community.get("telegram_channel_user_count"))
    watchlist_users = _to_int(asset.get("watchlist_portfolio_users"))

    posts_24h = None
    if reddit_posts_48h is not None and reddit_posts_48h > 0:
        posts_24h = reddit_posts_48h / 2.0
    elif reddit_active_48h is not None and reddit_active_48h > 0:
        posts_24h = reddit_active_48h / 8.0

    posts_60m = None
    if posts_24h is not None and posts_24h > 0:
        posts_60m = posts_24h / 24.0

    unique_authors_24h = None
    if reddit_active_48h is not None and reddit_active_48h > 0:
        unique_authors_24h = int(round(reddit_active_48h / 2.0))

    # CoinGecko fallback is an attention proxy:
    # - volume proxy: audience size
    # - engagement proxy: reddit posts/comments tempo
    social_volume_24h = None
    reach_raw = 0.0
    for value in (
        twitter_followers,
        reddit_subscribers,
        telegram_users,
        watchlist_users,
    ):
        if value is not None and value > 0:
            reach_raw += float(value)
    if reach_raw > 0:
        social_volume_24h = int(round(reach_raw))

    social_engagement_24h = None
    if reddit_posts_48h is not None or reddit_comments_48h is not None:
        posts_48h = reddit_posts_48h or 0.0
        comments_48h = reddit_comments_48h or 0.0
        engagement_24h = (posts_48h + comments_48h) / 2.0
        if engagement_24h > 0:
            social_engagement_24h = int(round(engagement_24h))

    updated_s = _normalize_ts_s(asset.get("last_updated") or asset.get("updated_at"))
    updated_at = int(updated_s) if updated_s is not None else _now_ts()

    metrics = _empty_social_metrics(source="coingecko")
    metrics.update(
        {
            "social_volume_24h": social_volume_24h,
            "social_engagement_24h": social_engagement_24h,
            "social_dominance_24h": None,
            "sentiment_24h": None,
            "social_rank": None,
            "social_heat": None,
            "social_heat_trend": None,
            "posts_60m": (
                int(round(posts_60m))
                if posts_60m is not None and posts_60m > 0
                else None
            ),
            "posts_24h": (
                int(round(posts_24h))
                if posts_24h is not None and posts_24h > 0
                else None
            ),
            "unique_authors_24h": unique_authors_24h,
            "source": "coingecko",
            "updated_at": updated_at,
        }
    )

    if not any(
        _is_meaningful_metric(metrics.get(key))
        for key in (
            "social_volume_24h",
            "social_engagement_24h",
            "posts_24h",
            "unique_authors_24h",
        )
    ):
        return None
    return metrics


def fetch_coingecko_social_metrics(symbol: str | None) -> dict[str, Any]:
    sym = _normalize_symbol(symbol)
    now_ts = _now_ts()
    if not sym:
        return {
            "status": "offline",
            "metrics": None,
            "ts": now_ts,
            "error": "symbol_missing",
        }

    cache_key = f"coingecko:social:{sym}"
    cached = _cache_get(cache_key)
    if cached and isinstance(cached.get("payload"), dict):
        age = _now_s() - float(cached.get("ts") or 0.0)
        payload = dict(cached.get("payload") or {})
        if age < _SOCIAL_TTL_S:
            return payload

    coin_id = coingecko_coin_id(sym)
    if not coin_id:
        if cached and isinstance(cached.get("payload"), dict):
            payload = dict(cached.get("payload") or {})
            payload["status"] = "degraded"
            payload["ts"] = now_ts
            payload["error"] = "coin_not_found"
            return payload
        return {
            "status": "offline",
            "metrics": None,
            "ts": now_ts,
            "error": "coin_not_found",
        }

    url = _COINGECKO_COIN_URL.format(coin_id=quote(coin_id, safe=""))
    status, data, err = _http_get_json(url)
    if status == 200 and isinstance(data, dict):
        metrics = _normalize_coingecko_metrics(data, sym, coin_id)
        if metrics is not None:
            payload = {
                "status": "live",
                "metrics": metrics,
                "coin_id": coin_id,
                "ts": now_ts,
            }
            _cache_set(cache_key, payload)
            return payload
        err = "invalid_payload"

    if cached and isinstance(cached.get("payload"), dict):
        payload = dict(cached.get("payload") or {})
        payload["status"] = "degraded"
        payload["ts"] = now_ts
        payload["error"] = "rate_limited" if status == 429 else (err or "unavailable")
        return payload

    return {
        "status": "offline",
        "metrics": None,
        "coin_id": coin_id,
        "ts": now_ts,
        "error": "rate_limited" if status == 429 else (err or "unavailable"),
    }


def _extract_lunar_asset(payload: Any, symbol: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    candidates: list[dict[str, Any]] = []

    if isinstance(data, list):
        candidates = [row for row in data if isinstance(row, dict)]
    elif isinstance(data, dict):
        candidates = [data]
    elif isinstance(payload, list):
        candidates = [row for row in payload if isinstance(row, dict)]
    else:
        candidates = [payload] if isinstance(payload, dict) else []

    if not candidates:
        return None

    for row in candidates:
        row_symbol = _normalize_symbol(row.get("symbol"))
        if row_symbol and row_symbol == symbol:
            return row

    return candidates[0]


def _normalize_lunar_heat(value: Any) -> float | None:
    n = _to_float(value)
    if n is None:
        return None
    if n <= 1.0:
        n *= 100.0
    elif n <= 10.0:
        n *= 10.0
    return round(_clamp(n, 0.0, 100.0), 1)


def _normalize_lunar_metrics(payload: Any, symbol: str) -> dict[str, Any] | None:
    asset = _extract_lunar_asset(payload, symbol)
    if not isinstance(asset, dict):
        return None

    volume_24h = _to_int(
        asset.get("social_volume_24h")
        or asset.get("social_volume")
        or asset.get("social_mentions")
    )
    engagement_24h = _to_int(
        asset.get("social_engagement_24h")
        or asset.get("social_engagement")
        or asset.get("social_interactions_24h")
        or asset.get("social_impact_score")
    )
    dominance = _to_float(
        asset.get("social_dominance_24h") or asset.get("social_dominance")
    )
    if dominance is not None:
        if dominance <= 1.0:
            dominance *= 100.0
        dominance = round(_clamp(dominance, 0.0, 100.0), 2)

    sentiment_payload = _coerce_sentiment_payload(
        asset.get("sentiment_24h")
        or asset.get("average_sentiment")
        or asset.get("sentiment")
    )

    social_rank = _to_int(asset.get("social_rank") or asset.get("alt_rank"))
    social_heat = _normalize_lunar_heat(
        asset.get("social_heat")
        or asset.get("social_score")
        or asset.get("galaxy_score")
    )
    posts_60m = _to_int(
        asset.get("social_volume_1h") or asset.get("social_mentions_1h")
    )
    posts_24h = volume_24h
    unique_authors = _to_int(
        asset.get("social_contributors") or asset.get("social_contributors_24h")
    )
    updated_at = (
        asset.get("time")
        or asset.get("updated_at")
        or asset.get("last_updated")
        or _now_ts()
    )

    heat_trend = None
    vol_change_24h = _to_float(
        asset.get("social_volume_change_24h") or asset.get("social_volume_change")
    )
    if vol_change_24h is not None:
        if vol_change_24h >= 15:
            heat_trend = "rising"
        elif vol_change_24h <= -15:
            heat_trend = "collapsing"
        else:
            heat_trend = "flat"
    elif posts_60m is not None and posts_24h is not None and posts_24h > 0:
        expected_hourly = max(1.0, posts_24h / 24.0)
        ratio = posts_60m / expected_hourly
        if ratio >= 1.5:
            heat_trend = "rising"
        elif ratio <= 0.6:
            heat_trend = "collapsing"
        else:
            heat_trend = "flat"

    metrics = _empty_social_metrics(source="lunarcrush")
    metrics.update(
        {
            "social_volume_24h": volume_24h,
            "social_engagement_24h": engagement_24h,
            "social_dominance_24h": dominance,
            "sentiment_24h": sentiment_payload,
            "social_rank": social_rank,
            "social_heat": social_heat,
            "social_heat_trend": heat_trend,
            "posts_60m": posts_60m,
            "posts_24h": posts_24h,
            "unique_authors_24h": unique_authors,
            "source": "lunarcrush",
            "updated_at": updated_at,
        }
    )

    if not any(
        _is_meaningful_metric(metrics.get(key))
        for key in (
            "social_volume_24h",
            "social_engagement_24h",
            "social_dominance_24h",
            "social_heat",
            "sentiment_24h",
        )
    ):
        return None
    return metrics


def fetch_lunarcrush_social_metrics(symbol: str | None) -> dict[str, Any]:
    sym = _normalize_symbol(symbol)
    now_ts = _now_ts()
    if not sym:
        return {
            "status": "offline",
            "metrics": None,
            "ts": now_ts,
            "error": "symbol_missing",
        }

    api_key = (
        os.getenv("LUNARCRUSH_API_KEY") or os.getenv("LUNARCRUSH_KEY") or ""
    ).strip()
    if not api_key:
        return {
            "status": "offline",
            "metrics": None,
            "ts": now_ts,
            "error": "not_configured",
        }

    cache_key = f"lunarcrush:metrics:{sym}"
    cached = _cache_get(cache_key)
    if cached and isinstance(cached.get("payload"), dict):
        age = _now_s() - float(cached.get("ts") or 0.0)
        payload = dict(cached.get("payload") or {})
        if age < _SOCIAL_TTL_S:
            return payload

    params = {
        "data": "assets",
        "symbol": sym,
        "key": api_key,
    }
    url = f"{_LUNARCRUSH_URL}?{urlencode(params)}"
    status, data, err = _http_get_json(url)

    if status == 200:
        metrics = _normalize_lunar_metrics(data, sym)
        if metrics is not None:
            payload = {
                "status": "live",
                "metrics": metrics,
                "ts": now_ts,
            }
            _cache_set(cache_key, payload)
            return payload
        err = "invalid_payload"

    if cached and isinstance(cached.get("payload"), dict):
        payload = dict(cached.get("payload") or {})
        payload["status"] = "degraded"
        payload["ts"] = now_ts
        payload["error"] = "rate_limited" if status == 429 else (err or "unavailable")
        return payload

    return {
        "status": "offline",
        "metrics": None,
        "ts": now_ts,
        "error": "rate_limited" if status == 429 else (err or "unavailable"),
    }


def _merge_metrics(
    primary: dict[str, Any], fallback: dict[str, Any], *, source: str
) -> dict[str, Any]:
    merged = dict(fallback or {})
    for key, value in (primary or {}).items():
        if value is None:
            continue
        merged[key] = value
    merged["source"] = source
    if merged.get("updated_at") is None:
        merged["updated_at"] = _now_ts()
    return merged


def _resolve_social_metrics(symbol: str, social_feed: dict[str, Any]) -> dict[str, Any]:
    fallback_bundle = _derive_coinpaprika_metrics(symbol, social_feed)
    fallback_metrics = dict(
        fallback_bundle.get("metrics") or _empty_social_metrics(source="coinpaprika")
    )
    fallback_status = str(fallback_bundle.get("status") or "offline")

    metric_keys = (
        "social_volume_24h",
        "social_engagement_24h",
        "social_dominance_24h",
        "social_heat",
        "sentiment_24h",
        "posts_24h",
        "posts_60m",
        "unique_authors_24h",
    )

    merged_metrics = fallback_metrics
    statuses = [fallback_status]
    errors: list[str] = []

    fallback_has_data = any(
        _is_meaningful_metric(fallback_metrics.get(k)) for k in metric_keys
    )
    should_try_gecko = any(
        not _is_meaningful_metric(fallback_metrics.get(k))
        for k in ("social_volume_24h", "social_engagement_24h")
    )

    if should_try_gecko:
        gecko_bundle = fetch_coingecko_social_metrics(symbol)
        gecko_status = str(gecko_bundle.get("status") or "offline")
        gecko_metrics = gecko_bundle.get("metrics")
        if isinstance(gecko_metrics, dict):
            current_source = str(merged_metrics.get("source") or "").strip().lower()
            if fallback_has_data and current_source and current_source != "coingecko":
                merged_source = current_source
            else:
                merged_source = "coingecko"
            # Fallback merge: keep existing values and only backfill missing fields.
            merged_metrics = _merge_metrics(
                primary=merged_metrics,
                fallback=gecko_metrics,
                source=merged_source,
            )
            statuses.append("live" if gecko_status == "live" else gecko_status)
        else:
            statuses.append(gecko_status)
        gecko_error = str(gecko_bundle.get("error") or "").strip()
        if gecko_error:
            errors.append(gecko_error)

    lunar_bundle = fetch_lunarcrush_social_metrics(symbol)
    lunar_status = str(lunar_bundle.get("status") or "offline")
    lunar_metrics = lunar_bundle.get("metrics")

    if isinstance(lunar_metrics, dict):
        has_base_data = any(
            _is_meaningful_metric(merged_metrics.get(k)) for k in metric_keys
        )
        merged_metrics = _merge_metrics(
            primary=lunar_metrics,
            fallback=merged_metrics,
            source="mixed" if has_base_data else "lunarcrush",
        )
        statuses.append("degraded" if lunar_status == "degraded" else "live")
    elif lunar_status == "degraded":
        statuses.append("degraded")
    lunar_error = str(lunar_bundle.get("error") or "").strip()
    if lunar_error:
        errors.append(lunar_error)

    out_status = _aggregate_status(*statuses)
    out = {
        "status": out_status,
        "metrics": merged_metrics,
        "ts": _now_ts(),
    }
    if errors and out_status in {"degraded", "offline"}:
        out["error"] = errors[0]
    return out


def fetch_coin_intel(symbol: str | None) -> dict[str, Any]:
    sym = _normalize_symbol(symbol)
    now_ts = _now_ts()
    if not sym:
        events = {"status": "offline", "items": []}
        social = {
            "status": "offline",
            "items": [],
            "metrics": _empty_social_metrics(source="none"),
        }
        return {
            "symbol": "",
            "status": "offline",
            "events": events,
            "news": events,
            "social": social,
            "ts": now_ts,
            "error": "symbol_missing",
        }

    coin_id = coinpaprika_coin_id(sym)
    if not coin_id:
        gecko_id = coingecko_coin_id(sym)
        events = {"status": "offline", "items": [], "error": "coin_not_found"}
        social_seed = {
            "status": "offline",
            "items": [],
            "error": "coin_not_found",
        }
        social_metrics = _resolve_social_metrics(sym, social_seed)
        social = dict(social_seed)
        social["metrics"] = dict(
            social_metrics.get("metrics") or _empty_social_metrics(source="none")
        )
        social["status"] = _aggregate_status(
            social.get("status"), social_metrics.get("status")
        )
        if social_metrics.get("error"):
            social["error"] = social_metrics.get("error")
        status = _aggregate_status(events.get("status"), social.get("status"))
        return {
            "symbol": sym,
            "coin_id": gecko_id or None,
            "status": status,
            "events": events,
            "news": events,
            "social": social,
            "ts": now_ts,
        }

    events = fetch_coinpaprika_events(coin_id)
    social = fetch_coinpaprika_twitter(coin_id)
    social_metrics = _resolve_social_metrics(sym, social)

    social_payload = dict(social)
    social_payload["metrics"] = dict(
        social_metrics.get("metrics") or _empty_social_metrics(source="none")
    )
    social_payload["status"] = _aggregate_status(
        social_payload.get("status"), social_metrics.get("status")
    )

    if social_metrics.get("error"):
        social_payload["error"] = social_metrics.get("error")

    status = _aggregate_status(events.get("status"), social_payload.get("status"))

    return {
        "symbol": sym,
        "coin_id": coin_id,
        "status": status,
        "events": events,
        "news": events,
        "social": social_payload,
        "ts": now_ts,
    }
