import React, { useCallback, memo } from "react";
import { useWatchlist } from "../context/WatchlistContext.jsx";
import { useSentiment } from "../context/SentimentContext.jsx";
import { formatPrice, formatPct } from "../utils/format.js";
import { classForDelta } from "../theme/brandTokens.js";

// TokenRow: table-row version used by legacy list panels and current movers.
function TokenRow({ row, token, item, index = 0, rank, changeKey, onInfo } = {}) {
  const data = row || token || item || {};
  const idx = Number.isFinite(index) ? index : 0;

  const rawSymbol = data.symbol || data.ticker || "";
  const display = rawSymbol?.replace(/-(USD|USDT|PERP)$/i, "") || rawSymbol || "--";

  const price = data.current_price ?? data.price ?? data.last_price ?? null;

  const pctRaw = changeKey
    ? data?.[changeKey]
    : (data.price_change_percentage_1min ?? data.price_change_1m ?? data.price_change_percentage_3min ?? data.price_change_1h ?? data.changePercent ?? 0);

  const pctNum = Number(pctRaw);
  const pct = Number.isFinite(pctNum) ? pctNum : 0;

  const { has, add, remove } = useWatchlist();
  const { sentiment } = useSentiment() || {};
  const starred = has(display);

  const toggleStar = useCallback(() => {
    if (!display || display === "--") return;
    if (starred) remove(display);
    else add({ symbol: display, price });
  }, [display, starred, add, remove, price]);

  return (
    <tr className={`table-row ${classForDelta(pct)}`} data-row="token">
      <td className="bh-token-rank">{rank ?? idx + 1}</td>
      <td className="bh-token-symbol">
        {display}
        {sentiment ? (
          <span className="sentiment-dot" title={`FG ${sentiment?.fear_greed?.value ?? "?"}`} aria-label="Sentiment indicator" />
        ) : null}
      </td>
      <td className="bh-token-price">{formatPrice(price)}</td>
      <td className={pct >= 0 ? "bh-token-change bh-token-change-up" : "bh-token-change bh-token-change-down"}>
        {formatPct(pct)}
      </td>
      <td className="bh-token-actions">
        <button type="button" onClick={toggleStar} className={starred ? "bh-star active" : "bh-star"} aria-label={starred ? "Remove from watchlist" : "Add to watchlist"}>
          ★
        </button>
        {onInfo && (
          <button type="button" onClick={() => onInfo(display)} className="bh-info" aria-label={`Show info for ${display}`}>
            ⓘ
          </button>
        )}
      </td>
    </tr>
  );
}

export default memo(TokenRow);
