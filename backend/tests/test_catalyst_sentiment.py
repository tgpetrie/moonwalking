import pytest
from defusedxml.common import DTDForbidden, EntitiesForbidden

from catalyst_sentiment import (
    CatalystSentimentAgent,
    CatalystSentimentService,
    parse_coingecko_trending,
    parse_reddit_atom,
    parse_rss,
    parse_telegram_html,
    structure_sentiment_posture,
)


@pytest.mark.parametrize("parser", [parse_rss, parse_reddit_atom])
@pytest.mark.parametrize(
    "document",
    [
        '<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///secret">]><rss>&xxe;</rss>',
        '<!DOCTYPE rss><rss/>',
    ],
)
def test_xml_external_entities_and_doctype_are_rejected(parser, document):
    with pytest.raises((DTDForbidden, EntitiesForbidden)):
        parser(document, "fixture")


def test_trending_parses_rank_and_usd_change():
    rows = parse_coingecko_trending(
        {"coins": [{"item": {"symbol": "btc", "name": "Bitcoin", "score": 0,
                             "data": {"price_change_percentage_24h": {"usd": 3.2}}}}]}
    )
    assert rows[0]["symbol"] == "BTC"
    assert rows[0]["rank"] == 1
    assert rows[0]["change_24h_pct"] == 3.2


def test_telegram_preview_parses_message_and_timestamp():
    page = ('<div class="tgme_widget_message_wrap">'
            '<div data-post="channel/42"><div class="tgme_widget_message_text">'
            'Bitcoin &amp; ETH<br>news</div><time datetime="2026-01-01T00:00:00Z">'
            '</time></div></div>')
    row = parse_telegram_html(page, "channel")[0]
    assert row["title"] == "Bitcoin & ETH news"
    assert row["url"] == "https://t.me/channel/42"
    assert row["ts"] is not None


def test_reddit_and_news_feed_parsers_extract_real_items():
    atom = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            '<id>t3_1</id><title>Bitcoin update</title>'
            '<updated>2026-01-01T00:00:00Z</updated>'
            '<link href="https://example.test/1"/><author><name>someone</name></author>'
            '</entry></feed>')
    rss = ('<rss><channel><item><title>ETH launch</title>'
           '<link>https://example.test/2</link>'
           '<pubDate>Thu, 01 Jan 2026 00:00:00 GMT</pubDate>'
           '</item></channel></rss>')
    assert parse_reddit_atom(atom, "Bitcoin")[0]["title"] == "Bitcoin update"
    assert parse_rss(rss, "news")[0]["title"] == "ETH launch"


@pytest.mark.parametrize(
    ("summary", "structure", "a1", "expected"),
    [
        ({"severe_negative": ["hack"]}, {}, False, "negative_catalyst_risk"),
        ({"hype": "high"}, {"reads": {"1h": {"active_pattern": "impulse_complete", "status": "complete", "bias": "bullish"}}}, False, "crowded_euphoria_top"),
        ({"catalyst_tone": "positive"}, {"reads": {"1h": {"active_pattern": "abc_in_progress", "status": "in_c_zone", "bias": "bullish"}}}, False, "catalyst_dip_reclaim"),
        ({"hype": "quiet"}, {"reads": {"1h": {"active_pattern": "abc_in_progress", "status": "in_c_zone", "bias": "bullish"}}}, True, "stealth_strength"),
        ({"trending_rank": 2}, {}, False, "trending_attention"),
        ({}, {}, False, "quiet"),
    ],
)
def test_structure_sentiment_postures(summary, structure, a1, expected):
    assert structure_sentiment_posture(summary, structure=structure, a1_pass=a1)["key"] == expected


def test_feed_cache_respects_ttl_and_reports_bad_xml():
    calls = []

    def get(url):
        calls.append(url)
        return 200, "<!DOCTYPE rss><rss/>"

    service = CatalystSentimentService(http_get=get, clock=lambda: 100, background=False)
    service._feed_specs = lambda: {"news:test": ("news", "https://example.test", lambda text: parse_rss(text, "test"))}
    service.refresh_due()
    service.refresh_due()
    assert len(calls) == 1
    assert service.source_health()["news:test"]["status"] == "parse_error"


def test_scout_emits_agent_observation():
    agent = CatalystSentimentAgent()
    observations = agent.run({"catalyst_sentiment": {"symbol": "BTC", "severe_negative": ["hack"]}})
    assert observations[0].agent == "sentiment_scout"
    assert observations[0].severity == "warning"
