import React from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { formatPrice, formatPct, tickerFromSymbol } from "../utils/format.js";
import { classForDelta } from "../theme/brandTokens.js";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";

// TokenRow: supports props row|token|item; strict <tr><td>… only
export default function TokenRow({ row, token, item, index = 0, rank, changeKey } = {}) {
  const data = row || token || item || {};
  const idx = Number.isFinite(index) ? index : 0;
  // Normalize symbol ("BTC-USD" -> "BTC")
  const rawSymbol = data.symbol || data.ticker || "";
  const symbol = rawSymbol && rawSymbol.includes("-") ? tickerFromSymbol(rawSymbol) : (rawSymbol || "—");
  // Price fallback chain
  const price = data.current_price ?? data.price ?? data.last_price ?? null;
  // Percent change (explicit key first, then common fallbacks)
  const pctRaw = changeKey
    ? data?.[changeKey]
    : (data.price_change_1m ?? data.price_change_percentage_3min ?? data.price_change_1h ?? data.changePercent ?? 0);
  const pctNum = Number(pctRaw);
  const pct = Number.isFinite(pctNum) ? pctNum : 0;
  // Watchlist / sentiment (per-row only; avoid global shared sentiment)
  const { has, add, remove } = useWatchlist();
  const starred = has(symbol);

  const sentimentRaw =
    data.sentiment ??
    data.sentiment_score ??
    data.overall_sentiment ??
    data.sentimentScore ??
    data.overallSentiment ??
    null;
  const sentimentObj = sentimentRaw && typeof sentimentRaw === "object" ? sentimentRaw : null;
  const sentimentScoreRaw = sentimentObj
    ? (sentimentObj.score ?? sentimentObj.overall_sentiment ?? sentimentObj.overallSentiment ?? sentimentObj.value ?? null)
    : sentimentRaw;
  const sentimentScoreNum = Number(sentimentScoreRaw);
  const sentimentScore = Number.isFinite(sentimentScoreNum) ? sentimentScoreNum : null;
  const sentimentPct = Number.isFinite(sentimentScore) ? (sentimentScore <= 1 ? Math.round(sentimentScore * 100) : Math.round(sentimentScore)) : null;
  const sentimentLabel =
    sentimentObj?.label ??
    sentimentObj?.classification ??
    data.sentiment_label ??
    data.sentimentLabel ??
    null;
  const sentimentString = typeof sentimentRaw === "string" ? sentimentRaw.trim() : "";
  const hasSentiment = sentimentPct != null || Boolean(sentimentString);
  const sentimentTitle =
    sentimentPct != null
      ? `Sentiment ${sentimentPct}%${sentimentLabel ? ` · ${sentimentLabel}` : ""}`
      : sentimentString
        ? `Sentiment ${sentimentString}`
        : undefined;
  function toggleStar() {
    if (!symbol || symbol === "—") return;
    if (starred) remove(symbol);
    else add({ symbol, price });
  }

  const url = coinbaseSpotUrl(data || {});
  const open = () => {
    if (!url) return;
    if (window.getSelection?.().toString()) return;
    window.open(url, "_blank", "noopener,noreferrer");
  };
  const handleClick = (e) => {
    if (e?.target?.closest && e.target.closest("a,button")) return;
    open();
  };

  return (
    <tr className={`table-row ${classForDelta(pct)} ${url ? 'bh-row-clickable' : ''}`} data-row="token" role={url ? 'link' : undefined} tabIndex={url ? 0 : undefined} onClick={handleClick} onKeyDown={(e)=>{ if(e.key==='Enter'||e.key===' ') { e.preventDefault(); handleClick(e); } }}>
      <td className="bh-token-rank">{rank ?? idx + 1}</td>
      <td className="bh-token-symbol">
        {symbol}
        {hasSentiment ? (
          <span className="sentiment-dot" title={sentimentTitle} aria-label="Sentiment indicator" />
        ) : null}
      </td>
      <td className="bh-token-price">{formatPrice(price)}</td>
      <td className={pct >= 0 ? "bh-token-change bh-token-change-up" : "bh-token-change bh-token-change-down"}>{formatPct(pct)}</td>
      <td className="bh-token-actions">
        <button type="button" onClick={toggleStar} className={starred ? "bh-star active" : "bh-star"} aria-label={starred ? "Remove from watchlist" : "Add to watchlist"}>
          ★
        </button>
      </td>
    </tr>
  );
}
