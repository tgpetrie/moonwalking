"""Zero-key social and catalyst sentiment, mapped to the coin universe.

Every source here is public and needs no API key or login:

- CoinGecko ``/search/trending`` (global trending list, 24h change) and, per
  coin on request, the crowd vote split from ``/coins/<id>``.
- Telegram public channel web previews (``https://t.me/s/<channel>``).
- Reddit ``.rss`` Atom feeds for a few subreddits.
- CoinTelegraph and Decrypt RSS.
- The alternative.me Fear & Greed index.

Fetching is polite and never blocks a request for long: each feed has its own
TTL, failures back off, and a stale feed is refreshed on a background thread
while the last good copy keeps serving. The parsers, the symbol matcher, the
catalyst classifier and the posture rules are pure functions so they can be
tested without the network.

Nothing here is outcome-validated. A posture describes the mix of chatter,
news and chart structure; it does not gate, rank or delay an alert.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import logging
import re
import threading
import time
from typing import Any, Callable, Iterable
from defusedxml import ElementTree

import requests

__all__ = [
    "TELEGRAM_CHANNELS",
    "REDDIT_SUBS",
    "NEWS_FEEDS",
    "parse_coingecko_trending",
    "parse_fear_greed",
    "parse_telegram_html",
    "parse_reddit_atom",
    "parse_rss",
    "parse_whale_alert",
    "classify_catalyst",
    "match_symbols",
    "build_universe",
    "summarize_symbol",
    "sentiment_posture",
    "structure_sentiment_posture",
    "CatalystSentimentAgent",
    "CatalystSentimentService",
    "get_service",
]

logger = logging.getLogger(__name__)

# A descriptive client name rather than a browser string: Reddit asks automated
# readers to identify themselves, and nothing here needs to look like a person.
USER_AGENT = "moonwalking-catalyst-reader/1.0 (read-only public feeds)"
HTTP_TIMEOUT_S = 6

TELEGRAM_CHANNELS = ("WatcherGuru", "whale_alert_io", "unfolded", "wublockchainenglish")
REDDIT_SUBS = ("CryptoCurrency", "solana", "Bitcoin", "altcoin")
NEWS_FEEDS = {
    "cointelegraph": "https://cointelegraph.com/rss",
    "decrypt": "https://decrypt.co/feed",
}
OPTIONAL_NEWS_FEEDS = {
    "vitalik_blog": "https://vitalik.eth.limo/feed.xml",
    "arthur_hayes": "https://cryptohayes.substack.com/feed",
}
# Curated mentions, not a verified list of followers or authorship.
VIP_INFLUENCER_GRAPH = (
    ("Vitalik Buterin", "@VitalikButerin", 1, 1.8, "ETH", ()),
    ("Changpeng Zhao", "@cz_binance", 1, 2.0, "BNB/BTC", ("CZ",)),
    ("Michael Saylor", "@saylor", 1, 1.7, "BTC", ()),
    ("Arthur Hayes", "@CryptoHayes", 1, 2.0, "macro/perps", ()),
    ("Elon Musk", "@elonmusk", 1, 2.2, "DOGE/BTC", ()),
    ("PlanB", "@100trillionUSD", 1, 1.5, "BTC", ()),
    ("Anthony Pompliano", "@APompliano", 1, 1.4, "BTC", ("Pomp",)),
    ("Balaji Srinivasan", "@balajis", 1, 1.5, "macro", ()),
    ("Robert Kiyosaki", "@theRealKiyosaki", 1, 1.2, "BTC", ()),
    ("James Wynn", "@JamesWynnReal", 1, 1.6, "perps/high-beta", ("Jwynn",)),
    ("Cobie", "@cobie", 2, 2.2, "alpha", ()),
    ("Pentoshi", "@Pentosh1", 2, 2.1, "alpha", ()),
    ("Andrew Kang", "@Rewkang", 2, 2.0, "alpha", ()),
    ("Julien Bittel", "@BittelJulien", 2, 2.0, "BTC", ()),
    ("Lyn Alden", "@LynAldenContact", 2, 1.9, "BTC", ()),
    ("Willy Woo", "@woonomic", 2, 1.8, "BTC", ()),
    ("Rekt Capital", "@rektcapital", 2, 1.9, "alpha", ()),
    ("DonAlt", "@CryptoDonAlt", 2, 1.9, "alpha", ()),
    ("Mert Mumtaz", "@0xMert_", 2, 1.9, "SOL", ()),
    ("Jesse Pollak", "@jessepollak", 2, 1.8, "BASE/ETH", ()),
    ("Lookonchain", "@lookonchain", 2, 1.8, "onchain", ()),
    ("ZackXBT", "@zachxbt", 2, 3.0, "security_sleuth", ()),
)


def match_vips(text: str) -> list[dict[str, Any]]:
    matched = []
    for name, handle, tier, weight, category, aliases in VIP_INFLUENCER_GRAPH:
        terms = (name, handle, *aliases)
        if any(re.search(r"(?<![A-Za-z0-9_])" + re.escape(term) + r"(?![A-Za-z0-9_])", text or "", re.I) for term in terms):
            matched.append({"name": name, "handle": handle, "tier": tier, "category": category, "weight": weight})
    return matched
COINGECKO_TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"
COINGECKO_COIN_URL = (
    "https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false"
    "&market_data=false&community_data=false&developer_data=false&sparkline=false"
)
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"

TTL_S = {
    "trending": 300,
    "fear_greed": 3600,
    "telegram": 180,
    "reddit": 300,
    "news": 300,
    "votes": 900,
}
FAILURE_BACKOFF_S = 300
RATE_LIMIT_BACKOFF_S = 900
INITIAL_WAIT_S = 3.0
WINDOW_S = 24 * 60 * 60
RECENT_S = 6 * 60 * 60

# ─── small helpers ────────────────────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _clean(fragment: str | None) -> str:
    """HTML fragment to one line of plain text."""
    if not fragment:
        return ""
    text = re.sub(r"<br\s*/?>", " ", fragment, flags=re.I)
    text = _TAG_RE.sub("", text)
    return _SPACE_RE.sub(" ", html.unescape(text)).strip()


def _ts_iso(value: str | None) -> float | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.timestamp()


def _ts_rfc822(value: str | None) -> float | None:
    if not value:
        return None
    try:
        stamp = parsedate_to_datetime(value.strip())
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.timestamp()


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and abs(out) != float("inf") else None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# ─── parsers (pure) ───────────────────────────────────────────────────────────


def parse_coingecko_trending(payload: Any) -> list[dict[str, Any]]:
    """Trending coins in CoinGecko's order, rank 1 first."""
    coins = payload.get("coins") if isinstance(payload, dict) else None
    out = []
    for position, entry in enumerate(coins or []):
        item = entry.get("item") if isinstance(entry, dict) else None
        if not isinstance(item, dict) or not item.get("symbol"):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        change = data.get("price_change_percentage_24h")
        change_usd = _num(change.get("usd")) if isinstance(change, dict) else _num(change)
        score = item.get("score")
        out.append(
            {
                "symbol": str(item["symbol"]).upper(),
                "name": str(item.get("name") or ""),
                "id": item.get("id"),
                "rank": (int(score) + 1) if isinstance(score, int) else position + 1,
                "market_cap_rank": item.get("market_cap_rank"),
                "change_24h_pct": change_usd,
            }
        )
    out.sort(key=lambda row: row["rank"])
    return out


def parse_fear_greed(payload: Any) -> dict[str, Any] | None:
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not rows or not isinstance(rows[0], dict):
        return None
    value = _num(rows[0].get("value"))
    if value is None:
        return None
    return {
        "value": int(value),
        "label": str(rows[0].get("value_classification") or ""),
        "ts": _num(rows[0].get("timestamp")),
    }


_TG_SPLIT_RE = re.compile(r'<div class="tgme_widget_message_wrap')
_TG_TEXT_RE = re.compile(
    r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S
)
_TG_TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"')
_TG_POST_RE = re.compile(r'data-post="([^"]+)"')


def parse_telegram_html(page: str, channel: str) -> list[dict[str, Any]]:
    """Messages from a ``t.me/s/<channel>`` preview page, oldest first."""
    out = []
    for chunk in _TG_SPLIT_RE.split(page or "")[1:]:
        body = _TG_TEXT_RE.search(chunk)
        text = _clean(body.group(1)) if body else ""
        if not text:
            continue
        post = _TG_POST_RE.search(chunk)
        stamp = _TG_TIME_RE.search(chunk)
        post_id = post.group(1) if post else None
        out.append(
            {
                "source": "telegram",
                "outlet": channel,
                "id": f"tg:{post_id}" if post_id else f"tg:{channel}:{hash(text)}",
                "ts": _ts_iso(stamp.group(1)) if stamp else None,
                "title": text[:280],
                "url": f"https://t.me/{post_id}" if post_id else f"https://t.me/s/{channel}",
            }
        )
    return out


def parse_reddit_atom(document: str, sub: str) -> list[dict[str, Any]]:
    """Post titles from a Reddit ``.rss`` Atom feed. Moderator threads are skipped."""
    root = ElementTree.fromstring(document, forbid_dtd=True, forbid_entities=True)
    out = []
    for entry in root:
        if _local(entry.tag) != "entry":
            continue
        fields = {_local(child.tag): child for child in entry}
        author = fields.get("author")
        name = ""
        if author is not None:
            for child in author:
                if _local(child.tag) == "name":
                    name = child.text or ""
        if name.endswith("AutoModerator"):
            continue
        title = _clean(fields["title"].text if "title" in fields else "")
        if not title:
            continue
        link = fields.get("link")
        stamp = fields.get("updated") if "updated" in fields else fields.get("published")
        out.append(
            {
                "source": "reddit",
                "outlet": f"r/{sub}",
                "id": f"reddit:{(fields['id'].text if 'id' in fields else title)}",
                "ts": _ts_iso(stamp.text if stamp is not None else None),
                "title": title[:280],
                "url": link.get("href") if link is not None else None,
            }
        )
    return out


def parse_rss(document: str, outlet: str) -> list[dict[str, Any]]:
    """Headlines from an RSS 2.0 feed."""
    root = ElementTree.fromstring(document, forbid_dtd=True, forbid_entities=True)
    out = []
    for item in root.iter():
        if _local(item.tag) != "item":
            continue
        fields = {_local(child.tag): child.text or "" for child in item}
        title = _clean(fields.get("title"))
        if not title:
            continue
        url = (fields.get("link") or fields.get("guid") or "").strip()
        out.append(
            {
                "source": "news",
                "outlet": outlet,
                "id": f"news:{url or title}",
                "ts": _ts_rfc822(fields.get("pubDate")),
                "title": title[:280],
                "summary": _clean(fields.get("description"))[:400],
                "url": url or None,
            }
        )
    return out


_EXCHANGES = (
    "coinbase", "binance", "kraken", "okx", "okex", "bybit", "bitfinex", "bitstamp",
    "kucoin", "gemini", "htx", "huobi", "gate", "mexc", "bitget", "upbit", "robinhood",
)
_WHALE_USD_RE = re.compile(r"\(([\d,]+(?:\.\d+)?)\s*USD\)", re.I)
_WHALE_ASSET_RE = re.compile(r"#([A-Za-z0-9]{2,12})")


def parse_whale_alert(text: str) -> dict[str, Any] | None:
    """Read a Whale Alert message: asset, USD size, and which way it moved."""
    lower = (text or "").lower()
    usd = _WHALE_USD_RE.search(text or "")
    if not usd:
        return None
    assets = [a.upper() for a in _WHALE_ASSET_RE.findall(text or "")]
    exchanges = [a for a in assets if a.lower() in _EXCHANGES]
    coins = [a for a in assets if a.lower() not in _EXCHANGES]
    if not coins:
        return None
    if "minted" in lower:
        action = "mint"
    elif "burned" in lower or "burnt" in lower:
        action = "burn"
    elif "unlocked" in lower:
        action = "unlock"
    elif "transferred" in lower:
        frm = re.search(r"from\s+#?(\w+)", lower)
        to = re.search(r"to\s+#?(\w+)", lower)
        from_ex = bool(frm and frm.group(1) in _EXCHANGES)
        to_ex = bool(to and to.group(1) in _EXCHANGES)
        if to_ex and not from_ex:
            action = "exchange_inflow"
        elif from_ex and not to_ex:
            action = "exchange_outflow"
        else:
            action = "transfer"
    else:
        action = "transfer"
    return {
        "asset": coins[0],
        "usd": float(usd.group(1).replace(",", "")),
        "action": action,
        "exchanges": exchanges,
    }


# ─── catalysts ────────────────────────────────────────────────────────────────

POSITIVE_CATALYSTS = {
    "listing": r"\b(?:will list|lists|listed|listing|new listing|now live on)\b",
    "mainnet": r"\bmainnet\b",
    "etf": r"\betfs?\b",
    "partnership": r"\bpartner(?:s|ship|ships|ed|ing)?\b",
    "approval": r"\bapprov(?:e|es|ed|al)\b",
    "upgrade": r"\bupgrade[sd]?\b",
    "launch": r"\blaunch(?:es|ed)?\b",
    "buyback": r"\bbuy ?backs?\b",
    "integration": r"\bintegrat(?:es|ed|ion)\b",
}
NEGATIVE_CATALYSTS = {
    "hack": r"\bhack(?:s|ed|er|ers)?\b",
    "exploit": r"\bexploit(?:s|ed)?\b",
    "delist": r"\bdelist(?:s|ed|ing)?\b",
    "unlock": r"\b(?:token )?unlock(?:s|ed)?\b",
    "lawsuit": r"\b(?:lawsuit|sues|sued|charged|indicted)\b",
    "outage": r"\b(?:outage|halts?|halted|paused withdrawals|suspend(?:s|ed)? withdrawals)\b",
    "drain": r"\bdrain(?:s|ed)?\b",
    "rug_pull": r"\brug ?pull(?:ed)?\b",
    "bankruptcy": r"\bbankrupt(?:cy)?\b",
}
# Tags that override everything else in the posture: real damage, not noise.
SEVERE_NEGATIVE = {"hack", "exploit", "delist", "drain", "rug_pull", "bankruptcy"}
_POS = {k: re.compile(v, re.I) for k, v in POSITIVE_CATALYSTS.items()}
_NEG = {k: re.compile(v, re.I) for k, v in NEGATIVE_CATALYSTS.items()}


def classify_catalyst(text: str) -> dict[str, Any]:
    """Catalyst tags in a headline and the net tone they give it."""
    positive = [tag for tag, rx in _POS.items() if rx.search(text or "")]
    negative = [tag for tag, rx in _NEG.items() if rx.search(text or "")]
    lower = (text or "").lower()
    # ETF outflows and rejected approvals read the other way.
    if "etf" in positive and re.search(r"\boutflows?\b", lower):
        positive.remove("etf")
        negative.append("etf_outflow")
    if "approval" in positive and re.search(r"\b(?:reject|deny|denies|denied|delay)", lower):
        positive.remove("approval")
        negative.append("approval_denied")
    if positive and negative:
        tone = "negative" if set(negative) & SEVERE_NEGATIVE else "mixed"
    elif negative:
        tone = "negative"
    elif positive:
        tone = "positive"
    else:
        tone = "none"
    return {"positive": positive, "negative": negative, "tone": tone}


# ─── symbol matching ──────────────────────────────────────────────────────────

# Tickers that are also everyday words or common abbreviations; they only count
# when written as a cashtag ($ONE) or hashtag (#ONE).
AMBIGUOUS_TICKERS = {
    "A", "AI", "ALL", "AND", "ANY", "APP", "ARE", "BIG", "CAT", "CEO", "DAY", "DOG",
    "ETF", "FOR", "GAS", "GET", "GO", "HOT", "IT", "KEY", "MAX", "NEW", "NOW", "ONE",
    "OUT", "PEOPLE", "POL", "RAY", "SEC", "SUN", "THE", "TOP", "TRUMP", "UP", "USA",
    "USD", "WIN", "YOU", "LOW", "FUN", "BOND", "MOVE", "SAFE", "JUST", "OPEN", "REAL",
}
# Names that are also everyday words.
AMBIGUOUS_NAMES = {"near", "maker", "gas", "one", "polygon zkevm", "stellar", "chain"}
MAJOR_NAMES: dict[str, tuple[str, ...]] = {
    "BTC": ("bitcoin",), "ETH": ("ethereum", "ether"), "SOL": ("solana",),
    "XRP": ("ripple", "xrp"), "ADA": ("cardano",), "DOGE": ("dogecoin",),
    "AVAX": ("avalanche",), "LINK": ("chainlink",), "DOT": ("polkadot",),
    "LTC": ("litecoin",), "BCH": ("bitcoin cash",), "XLM": ("stellar lumens",),
    "UNI": ("uniswap",), "AAVE": ("aave",), "ATOM": ("cosmos",), "HBAR": ("hedera",),
    "SUI": ("sui network",), "APT": ("aptos",), "ARB": ("arbitrum",),
    "OP": ("optimism",), "INJ": ("injective",), "TIA": ("celestia",),
    "SHIB": ("shiba inu",), "PEPE": ("pepe",), "BONK": ("bonk",), "WIF": ("dogwifhat",),
    "HYPE": ("hyperliquid",), "ENA": ("ethena",), "TAO": ("bittensor",),
    "FET": ("fetch.ai",), "RENDER": ("render network",), "FIL": ("filecoin",),
    "ICP": ("internet computer",), "ALGO": ("algorand",), "ZEC": ("zcash",),
    "ONDO": ("ondo",), "JUP": ("jupiter",), "PENGU": ("pudgy penguins",),
    "ASTER": ("aster",), "SEI": ("sei network",), "KAS": ("kaspa",), "TON": ("toncoin",),
    "USDT": ("tether",), "USDC": ("usd coin",),
}


def build_universe(
    symbols: Iterable[str] = (),
    trending: Iterable[dict[str, Any]] = (),
    names: dict[str, Iterable[str]] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Symbol -> lowercase names to look for. Majors, trending coins, and extras."""
    universe: dict[str, set[str]] = {s: set(n) for s, n in MAJOR_NAMES.items()}
    for symbol in symbols:
        sym = str(symbol or "").upper().split("-")[0].strip()
        if re.fullmatch(r"[A-Z0-9]{1,15}", sym):
            universe.setdefault(sym, set())
    for row in trending:
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            continue
        name = str(row.get("name") or "").strip().lower()
        universe.setdefault(sym, set())
        if len(name) >= 4:
            universe[sym].add(name)
    for sym, extra in (names or {}).items():
        universe.setdefault(sym.upper(), set()).update(
            str(n).lower() for n in extra if len(str(n)) >= 4
        )
    return {sym: tuple(sorted(n)) for sym, n in universe.items()}


_CASHTAG_RE = re.compile(r"[$#]([A-Za-z][A-Za-z0-9]{0,11})\b")
_UPPER_RE = re.compile(r"(?<![A-Za-z0-9$#])([A-Z][A-Z0-9]{1,11})(?![A-Za-z0-9])")
_NAME_RX_CACHE: dict[str, re.Pattern] = {}


def match_symbols(text: str, universe: dict[str, tuple[str, ...]]) -> set[str]:
    """Universe symbols a piece of text talks about."""
    found: set[str] = set()
    if not text:
        return found
    for tag in _CASHTAG_RE.findall(text):
        if tag.upper() in universe:
            found.add(tag.upper())
    for token in _UPPER_RE.findall(text):
        if token in universe and len(token) >= 3 and token not in AMBIGUOUS_TICKERS:
            found.add(token)
    lower = text.lower()
    for sym, names in universe.items():
        if sym in found:
            continue
        for name in names:
            if name in AMBIGUOUS_NAMES or name not in lower:
                continue
            rx = _NAME_RX_CACHE.get(name)
            if rx is None:
                rx = re.compile(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])")
                _NAME_RX_CACHE[name] = rx
            if rx.search(lower):
                found.add(sym)
                break
    return found


# ─── per-symbol summary (pure) ────────────────────────────────────────────────


def summarize_symbol(
    symbol: str,
    items: Iterable[dict[str, Any]],
    *,
    universe: dict[str, tuple[str, ...]],
    trending: Iterable[dict[str, Any]] = (),
    fear_greed: dict[str, Any] | None = None,
    votes: dict[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Mentions, velocity, catalysts and hype for one coin over the last 24h."""
    sym = str(symbol or "").upper().split("-")[0]
    now = time.time() if now is None else now
    mentions: list[dict[str, Any]] = []
    for item in items:
        ts = item.get("ts")
        if ts is None or now - ts > WINDOW_S or ts - now > 600:
            continue
        text = f"{item.get('title') or ''} {item.get('summary') or ''}"
        hits = match_symbols(text, universe)
        whale = parse_whale_alert(item.get("title") or "") if item.get("outlet") == "whale_alert_io" else None
        if whale and whale["asset"] == sym:
            hits.add(sym)
        if sym not in hits:
            continue
        tags = classify_catalyst(text)
        vips = match_vips(text)
        mentions.append({**item, "tags": tags, "vip_mentions": vips, "sentiment_weight": max((v["weight"] for v in vips), default=1.0), "whale": whale if whale and whale["asset"] == sym else None})
    mentions.sort(key=lambda m: m["ts"], reverse=True)

    by_source: dict[str, int] = {}
    for m in mentions:
        by_source[m["source"]] = by_source.get(m["source"], 0) + 1
    recent = sum(1 for m in mentions if now - m["ts"] <= RECENT_S)
    earlier = len(mentions) - recent
    # Mentions per hour in the last 6h against the 18h before it.
    velocity = None
    if len(mentions) >= 3:
        velocity = round((recent / 6.0) / max(earlier / 18.0, 1.0 / 18.0), 2)

    positive = [m for m in mentions if m["tags"]["tone"] == "positive"]
    negative = [m for m in mentions if m["tags"]["tone"] == "negative"]
    severe = sorted({t for m in negative for t in m["tags"]["negative"] if t in SEVERE_NEGATIVE})
    vip_mentions = list({v["handle"]: v for m in mentions for v in m["vip_mentions"]}.values())
    cross_tier = {v["tier"] for v in vip_mentions} == {1, 2}
    bonus = 1.5 if cross_tier else 1.0
    weighted_positive = sum(m["sentiment_weight"] for m in positive) * bonus
    weighted_negative = sum(m["sentiment_weight"] for m in negative) * bonus
    security_mention = any(v["category"] == "security_sleuth" for v in vip_mentions)
    if severe or security_mention or (negative and weighted_negative > weighted_positive):
        catalyst_tone = "negative"
    elif positive and weighted_positive > weighted_negative:
        catalyst_tone = "positive"
    elif positive or negative:
        catalyst_tone = "mixed"
    else:
        catalyst_tone = "none"

    trend_row = next((t for t in trending if str(t.get("symbol")).upper() == sym), None)
    trend_rank = trend_row.get("rank") if trend_row else None

    score = 0
    if trend_rank is not None:
        score += 3 if trend_rank <= 7 else 2
    score += 2 if len(mentions) >= 8 else 1 if len(mentions) >= 3 else 0
    if velocity is not None and velocity >= 2.0 and recent >= 3:
        score += 1
    hype = "high" if score >= 4 else "elevated" if score >= 2 else "normal" if score >= 1 else "quiet"

    whales = [m["whale"] for m in mentions if m.get("whale")]
    catalysts = [
        {
            "title": m["title"],
            "source": m["source"],
            "outlet": m.get("outlet"),
            "url": m.get("url"),
            "ts": m["ts"],
            "tone": m["tags"]["tone"],
            "tags": m["tags"]["positive"] + m["tags"]["negative"],
        }
        for m in mentions
        if m["tags"]["tone"] != "none" or m.get("whale")
    ][:6]
    return {
        "symbol": sym,
        "mentions_24h": len(mentions),
        "mentions_6h": recent,
        "mentions_by_source": by_source,
        "velocity": velocity,
        "hype": hype,
        "hype_score": score,
        "trending_rank": trend_rank,
        "change_24h_pct": trend_row.get("change_24h_pct") if trend_row else None,
        "catalyst_tone": catalyst_tone,
        "positive_catalysts": len(positive),
        "negative_catalysts": len(negative),
        "weighted_positive": weighted_positive,
        "weighted_negative": weighted_negative,
        "vip_mentions": vip_mentions,
        "cross_tier_confluence": cross_tier,
        "cross_tier_multiplier": bonus,
        "negative_catalyst_risk": security_mention,
        "severe_negative": severe,
        "whale_flows": whales[:5],
        "catalysts": catalysts,
        "recent_mentions": [
            {"title": m["title"], "source": m["source"], "outlet": m.get("outlet"), "url": m.get("url"), "ts": m["ts"], "vip_mentions": m["vip_mentions"], "sentiment_weight": m["sentiment_weight"]}
            for m in mentions[:5]
        ],
        "votes": votes,
        "fear_greed": fear_greed,
    }


# ─── structure-aware posture (pure) ───────────────────────────────────────────

_REVIEW_NOTE = (
    "Context only: it does not block, rank or change any alert, and it has not "
    "been tested against outcomes."
)


def _reads(structure: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    reads = (structure or {}).get("reads") if isinstance(structure, dict) else None
    return reads if isinstance(reads, dict) else {}


def structure_sentiment_posture(
    summary: dict[str, Any],
    *,
    structure: dict[str, Any] | None = None,
    positioning: dict[str, Any] | None = None,
    a1_pass: bool | None = None,
) -> dict[str, Any]:
    """One plain posture from chatter, news, chart structure and perp positioning.

    ``structure`` is a ``chart_structure.radar_structure`` payload, and
    ``positioning`` a ``derivatives_positioning.get_symbol_positioning`` one.
    Returns a quiet posture when no specific pattern stands out.
    """
    reads = _reads(structure)
    radar = (structure or {}).get("posture") if isinstance(structure, dict) else None
    trend_4h = (structure or {}).get("trend_4h") if isinstance(structure, dict) else None
    hype = summary.get("hype") or "quiet"
    loud = hype in ("elevated", "high")
    funding = (positioning or {}).get("funding_bias") if isinstance(positioning, dict) else None

    def state(tf: str) -> tuple[str, str, str]:
        r = reads.get(tf) or {}
        return (str(r.get("active_pattern")), str(r.get("status")), str(r.get("bias")))

    extended = [tf for tf in ("4h", "1h", "15m") if state(tf) == ("impulse_complete", "complete", "bullish")]
    one_hour = state("1h")
    dip_or_reclaim = (
        (one_hour[0] == "abc_in_progress" and one_hour[1] == "in_c_zone" and one_hour[2] == "bullish")
        or (one_hour[0] == "abc_complete" and one_hour[1] == "confirmed" and one_hour[2] == "bullish")
        or (isinstance(radar, dict) and radar.get("key") in ("reclaiming_zone", "bounce_in_uptrend"))
    )
    constructive = (
        (isinstance(radar, dict) and radar.get("tone") == "constructive")
        or (one_hour[2] == "bullish" and one_hour[0] in ("abc_in_progress", "abc_complete", "impulse_in_progress"))
    )

    if summary.get("severe_negative") or summary.get("negative_catalyst_risk"):
        tag = summary["severe_negative"][0].replace("_", " ") if summary.get("severe_negative") else "security researcher mentioned"
        return {
            "key": "negative_catalyst_risk",
            "tone": "risk",
            "label": f"Negative catalyst · {tag}",
            "short_label": f"News: {tag}",
            "detail": f"Recent news or channel posts mention a {tag} for this coin. {_REVIEW_NOTE}",
        }
    if loud and (extended or funding == "crowded_long"):
        why = []
        if extended:
            why.append(f"a five-step run up looks finished on the {extended[0]} chart")
        if funding == "crowded_long":
            why.append("perp longs are crowded (high positive funding)")
        return {
            "key": "crowded_euphoria_top",
            "tone": "risk",
            "label": "Crowded euphoria at extended top" if extended else "Crowded euphoria · longs crowded",
            "short_label": "Crowded euphoria",
            "detail": (
                f"Chatter is {hype} while {' and '.join(why)}. In our Oct 13 to Nov 12 "
                f"review, gainer flags at the end of a finished run crashed more often. {_REVIEW_NOTE}"
            ),
        }
    if summary.get("catalyst_tone") == "positive" and dip_or_reclaim:
        return {
            "key": "catalyst_dip_reclaim",
            "tone": "constructive",
            "label": "Catalyst + dip zone / reclaim",
            "short_label": "Catalyst + dip",
            "detail": (
                "Positive news flow while the 1-hour chart is in its pullback zone or "
                f"stepping back up out of it. {_REVIEW_NOTE}"
            ),
        }
    if a1_pass and constructive and trend_4h != "down" and hype == "quiet":
        return {
            "key": "stealth_strength",
            "tone": "constructive",
            "label": "Stealth strength",
            "short_label": "Stealth strength",
            "detail": (
                "Strong 3-minute dollar flow (passes the A1 gate) and a constructive "
                f"chart, with almost no social chatter yet. {_REVIEW_NOTE}"
            ),
        }
    if loud or summary.get("trending_rank") is not None:
        rank = summary.get("trending_rank")
        return {
            "key": "trending_attention",
            "tone": "neutral",
            "label": f"Trending #{rank}" if rank else "In the spotlight",
            "short_label": f"Trending #{rank}" if rank else "Busy chatter",
            "detail": f"Chatter is {hype}; the chart does not add a clear read either way. {_REVIEW_NOTE}",
        }
    return {
        "key": "quiet",
        "tone": "neutral",
        "label": "Quiet",
        "short_label": "Quiet",
        "detail": f"No specific catalyst posture was identified. {_REVIEW_NOTE}",
    }


sentiment_posture = structure_sentiment_posture


class CatalystSentimentAgent:
    """Publish supplied, source-backed catalyst context without fetching feeds."""

    name = "sentiment_scout"
    model_version = "catalyst-sentiment-v1"

    def run(self, context: dict | None) -> list:
        context = context or {}
        summaries = context.get("catalyst_sentiments") or [context.get("catalyst_sentiment")]
        return [finding for summary in summaries for finding in self._read_symbol(context, summary)]

    def _read_symbol(self, context, summary):
        if not isinstance(summary, dict) or not summary.get("symbol"):
            return []
        posture = structure_sentiment_posture(
            summary,
            structure=context.get("structure"),
            positioning=context.get("positioning"),
            a1_pass=context.get("a1_pass"),
        )
        if posture["key"] == "quiet":
            return []
        try:
            from .agents.contracts import AgentObservation
        except ImportError:
            from agents.contracts import AgentObservation
        return [
            AgentObservation(
                agent=self.name,
                kind="catalyst_posture",
                symbol=str(summary["symbol"]),
                severity="warning" if posture["tone"] == "risk" else "info",
                summary=f"{summary['symbol']}: {posture['label']}. {posture['detail']}",
                evidence={"posture": posture, "catalysts": summary.get("catalysts", [])},
                source={"surface": "catalyst_sentiment"},
            )
        ]


# ─── fetching with TTL caches ─────────────────────────────────────────────────


class _Feed:
    __slots__ = ("items", "fetched_at", "status", "error", "next_ok_at", "refreshing")

    def __init__(self) -> None:
        self.items: Any = None
        self.fetched_at = 0.0
        self.status = "never"
        self.error: str | None = None
        self.next_ok_at = 0.0
        self.refreshing = False


class CatalystSentimentService:
    """Polite, cached access to every zero-key source.

    ``http_get(url) -> (status_code, text)`` and ``clock`` are injectable for
    tests. ``background=False`` refreshes inline, which tests also use.
    """

    def __init__(
        self,
        *,
        http_get: Callable[[str], tuple[int | None, str]] | None = None,
        clock: Callable[[], float] = time.time,
        background: bool = True,
        initial_wait_s: float = INITIAL_WAIT_S,
    ) -> None:
        self._http_get = http_get or self._default_get
        self._clock = clock
        self._background = background
        self._initial_wait_s = initial_wait_s
        self._lock = threading.Lock()
        self._feeds: dict[str, _Feed] = {}
        self._votes: dict[str, tuple[float, dict[str, Any] | None]] = {}

    @staticmethod
    def _default_get(url: str) -> tuple[int | None, str]:
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT_S)
            return resp.status_code, resp.text
        except Exception as exc:  # network trouble is a status, not a crash
            logger.debug("[CatalystSentiment] GET %s failed: %s", url, exc)
            return None, ""

    # Each feed: (kind for TTL, url, parser)
    def _feed_specs(self) -> dict[str, tuple[str, str, Callable[[str], Any]]]:
        import json

        specs: dict[str, tuple[str, str, Callable[[str], Any]]] = {
            "trending": ("trending", COINGECKO_TRENDING_URL, lambda t: parse_coingecko_trending(json.loads(t))),
            "fear_greed": ("fear_greed", FEAR_GREED_URL, lambda t: parse_fear_greed(json.loads(t))),
        }
        for channel in TELEGRAM_CHANNELS:
            specs[f"telegram:{channel}"] = (
                "telegram",
                f"https://t.me/s/{channel}",
                lambda t, c=channel: parse_telegram_html(t, c),
            )
        for sub in REDDIT_SUBS:
            specs[f"reddit:{sub}"] = (
                "reddit",
                f"https://www.reddit.com/r/{sub}/new/.rss",
                lambda t, s=sub: parse_reddit_atom(t, s),
            )
        for outlet, url in NEWS_FEEDS.items():
            specs[f"news:{outlet}"] = ("news", url, lambda t, o=outlet: parse_rss(t, o))
        for outlet, url in OPTIONAL_NEWS_FEEDS.items():
            specs[f"optional_news:{outlet}"] = ("news", url, lambda t, o=outlet: parse_rss(t, o))
        return specs

    def _refresh(self, name: str, kind: str, url: str, parse: Callable[[str], Any]) -> None:
        try:
            status, text = self._http_get(url)
        except requests.RequestException as exc:
            logger.warning("[CatalystSentiment] %s fetch failed: %s", name, exc)
            status, text = None, ""
        now = self._clock()
        with self._lock:
            feed = self._feeds.setdefault(name, _Feed())
            feed.refreshing = False
            if status == 200 and text:
                try:
                    parsed = parse(text)
                except Exception as exc:
                    logger.warning("[CatalystSentiment] %s parse failed: %s", name, exc)
                    feed.status, feed.error = "parse_error", str(exc)[:200]
                    feed.next_ok_at = now + FAILURE_BACKOFF_S
                    return
                feed.items, feed.fetched_at = parsed, now
                feed.status, feed.error = "ok", None
                feed.next_ok_at = now + TTL_S[kind]
                return
            limited = status == 429
            feed.status = "rate_limited" if limited else "unavailable"
            feed.error = f"HTTP {status}" if status else "no response"
            feed.next_ok_at = now + (RATE_LIMIT_BACKOFF_S if limited else FAILURE_BACKOFF_S)

    def refresh_due(self) -> None:
        """Start a refresh for every feed that is due. Never waits for the network
        except, briefly, on the very first call."""
        threads = []
        now = self._clock()
        first_load = False
        for name, (kind, url, parse) in self._feed_specs().items():
            with self._lock:
                feed = self._feeds.setdefault(name, _Feed())
                if feed.refreshing or now < feed.next_ok_at:
                    continue
                first_load = first_load or feed.items is None
                feed.refreshing = True
            if not self._background:
                self._refresh(name, kind, url, parse)
                continue
            thread = threading.Thread(
                target=self._refresh, args=(name, kind, url, parse), daemon=True
            )
            thread.start()
            threads.append(thread)
        if first_load and threads:
            deadline = time.monotonic() + self._initial_wait_s
            for thread in threads:
                thread.join(max(0.0, deadline - time.monotonic()))

    def _items(self, prefix: str) -> list[dict[str, Any]]:
        with self._lock:
            out = []
            for name, feed in self._feeds.items():
                if name.startswith(prefix) and feed.status == "ok" and self._clock() < feed.next_ok_at and isinstance(feed.items, list):
                    out.extend(feed.items)
            return out

    def _value(self, name: str) -> Any:
        with self._lock:
            feed = self._feeds.get(name)
            return feed.items if feed and feed.status == "ok" and self._clock() < feed.next_ok_at else None

    def source_health(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                name: {
                    "status": "stale" if feed.status == "ok" and self._clock() >= feed.next_ok_at else feed.status,
                    "fetched_at": feed.fetched_at or None,
                    "items": len(feed.items) if isinstance(feed.items, list) else (1 if feed.items else 0),
                    "error": feed.error,
                }
                for name, feed in sorted(self._feeds.items())
            }

    def votes(self, symbol: str) -> dict[str, Any] | None:
        """CoinGecko crowd vote split for one coin, cached. Never raises."""
        sym = str(symbol or "").upper()
        now = self._clock()
        hit = self._votes.get(sym)
        if hit and now - hit[0] < TTL_S["votes"]:
            return hit[1]
        result = None
        try:
            try:
                from coin_intel_external import coingecko_coin_id
            except ImportError:
                from backend.coin_intel_external import coingecko_coin_id
            coin_id = coingecko_coin_id(sym)
            if coin_id:
                import json

                status, text = self._http_get(COINGECKO_COIN_URL.format(coin_id=coin_id))
                if status == 200 and text:
                    data = json.loads(text)
                    up = _num(data.get("sentiment_votes_up_percentage"))
                    down = _num(data.get("sentiment_votes_down_percentage"))
                    if up is not None and down is not None:
                        result = {"up_pct": round(up, 1), "down_pct": round(down, 1), "coin_id": coin_id}
        except Exception as exc:
            logger.debug("[CatalystSentiment] votes for %s failed: %s", sym, exc)
        self._votes[sym] = (now, result)
        return result

    def all_items(self) -> list[dict[str, Any]]:
        seen, out = set(), []
        for item in self._items("telegram:") + self._items("reddit:") + self._items("news:") + self._items("optional_news:"):
            if item.get("id") in seen:
                continue
            seen.add(item.get("id"))
            out.append(item)
        return out

    def symbol(self, symbol: str, *, extra_symbols: Iterable[str] = (), with_votes: bool = False) -> dict[str, Any]:
        self.refresh_due()
        trending = self._value("trending") or []
        universe = build_universe([symbol, *extra_symbols], trending)
        return summarize_symbol(
            symbol,
            self.all_items(),
            universe=universe,
            trending=trending,
            fear_greed=self._value("fear_greed"),
            votes=self.votes(symbol) if with_votes else None,
            now=self._clock(),
        )

    def overview(self, symbols: Iterable[str] = (), *, limit: int = 12) -> dict[str, Any]:
        """Global mood, trending list and the newest catalysts across the universe."""
        self.refresh_due()
        trending = self._value("trending") or []
        universe = build_universe(symbols, trending)
        now = self._clock()
        latest = []
        for item in sorted(self.all_items(), key=lambda i: i.get("ts") or 0, reverse=True):
            if item.get("ts") is None or now - item["ts"] > WINDOW_S:
                continue
            tags = classify_catalyst(f"{item.get('title') or ''} {item.get('summary') or ''}")
            if tags["tone"] == "none":
                continue
            hits = sorted(match_symbols(f"{item.get('title') or ''} {item.get('summary') or ''}", universe))
            if not hits:
                continue
            latest.append({**{k: item.get(k) for k in ("title", "source", "outlet", "url", "ts")}, "symbols": hits, "tone": tags["tone"], "tags": tags["positive"] + tags["negative"]})
            if len(latest) >= limit:
                break
        return {
            "fear_greed": self._value("fear_greed"),
            "trending": trending[:15],
            "catalysts": latest,
            "sources": self.source_health(),
        }


_SERVICE: CatalystSentimentService | None = None
_SERVICE_LOCK = threading.Lock()


def get_service() -> CatalystSentimentService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = CatalystSentimentService(initial_wait_s=0)
        return _SERVICE
