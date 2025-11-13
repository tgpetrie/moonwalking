import React, { useCallback, memo } from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { useSentiment } from "../context/SentimentContext.jsx";
import { formatPrice, formatPct, tickerFromSymbol } from "../utils/format.js";
import { classForDelta } from "../theme/brandTokens.js";

// TokenRow: supports props row|token|item; strict <tr><td>… only
function TokenRow({ row, token, item, index = 0, rank, changeKey, onInfo } = {}) {
  const data = row || token || item || {};
  const idx = Number.isFinite(index) ? index : 0;

  // Normalize symbol ("BTC-USD" -> "BTC")
  const rawSymbol = data.symbol || data.ticker || "";
  const symbol =
    rawSymbol && rawSymbol.includes("-") ? tickerFromSymbol(rawSymbol) : (rawSymbol || "—");

  // Price fallback chain
  const price = data.current_price ?? data.price ?? data.last_price ?? null;

  // Percent change (explicit key first, then common fallbacks)
  const pctRaw = changeKey
    ? data?.[changeKey]
    : (
        data.price_change_percentage_1min ?? // 1-min percent from backend
        data.price_change_1m ??              // alt 1-min key, if ever used
        data.price_change_percentage_3min ?? // 3-min percent
        data.price_change_1h ??              // 1-hour percent
        data.changePercent ??                // generic fallback
        0
      );
  const pctNum = Number(pctRaw);
  const pct = Number.isFinite(pctNum) ? pctNum : 0;

  // Watchlist / sentiment
  const { has, add, remove } = useWatchlist();
  const { sentiment } = useSentiment() || {};
  const starred = has(symbol);

  const toggleStar = useCallback(() => {
    if (!symbol || symbol === "—") return;
    if (starred) {
      remove(symbol);
    } else {
      add({ symbol, price });
    }
  }, [symbol, starred, add, remove, price]);

  return (
    <tr className={`table-row ${classForDelta(pct)}`} data-row="token">
      <td className="bh-token-rank">{rank ?? idx + 1}</td>
      <td className="bh-token-symbol">
        {symbol}
        {sentiment ? (
          <span
            className="sentiment-dot"
            title={`FG ${sentiment?.fear_greed?.value ?? "?"}`}
            aria-label="Sentiment indicator"
          />
        ) : null}
      </td>
      <td className="bh-token-price">{formatPrice(price)}</td>
      <td className={pct >= 0 ? "bh-token-change bh-token-change-up"
                              : "bh-token-change bh-token-change-down"}>
        {formatPct(pct)}
      </td>
      <td className="bh-token-actions">
        <button
          type="button"
          onClick={toggleStar}
          className={starred ? "bh-star active" : "bh-star"}
          aria-label={starred ? "Remove from watchlist" : "Add to watchlist"}
        >
          ★
        </button>
        {onInfo && (
          <button
            type="button"
            onClick={() => onInfo(symbol)}
            className="bh-info"
            aria-label={`Show info for ${symbol}`}
          >
            ⓘ
          </button>
        )}
      </td>
    </tr>
  );
}

export default memo(TokenRow);
