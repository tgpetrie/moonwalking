import React, { memo } from "react";
import { useSentiment } from "../context/SentimentContext.jsx";
import { formatPrice, formatPct, tickerFromSymbol } from "../utils/format.js";
import RowActions from "./tables/RowActions.jsx";

// TokenRow: BHABIT-styled token row used by 1m/3m movers panels.
function TokenRow({
  row,
  token,
  item,
  index = 0,
  rank,
  changeKey,
  interval = "3m",
  onInfo,
  onHover,
  isLoss: explicitIsLoss,
} = {}) {
  // Support multiple calling conventions: row / token / item
  const data = row || token || item || {};
  const rawSymbol = data.symbol || data.ticker || "";
  const display = rawSymbol?.replace(/-(USD|USDT|PERP)$/i, "") || rawSymbol || "--";

  const price = data.current_price ?? data.price ?? data.last_price ?? null;
  const prevPrice =
    data.previous_price ??
    data.initial_price_1min ??
    data.initial_price_3min ??
    null;

  const pctRaw = changeKey
    ? data?.[changeKey]
    : (data.price_change_percentage_1min ?? data.price_change_1m ?? data.price_change_percentage_3min ?? data.price_change_1h ?? data.changePercent ?? 0);

  const pctNum = Number(pctRaw);
  const pct = Number.isFinite(pctNum) ? pctNum : 0;

  const { sentiment } = useSentiment() || {};

  const pctClass = pct < 0 ? "token-pct-loss" : "token-pct-gain";
  const streakRaw = data.trendStreak ?? data.trend_streak ?? data.peak_count ?? 0;
  const streak = Number.isFinite(Number(streakRaw)) ? Number(streakRaw) : 0;
  // Cap visible streak dots to avoid inflated counts; tooltip contains raw value.
  const streakDots = streak >= 1 ? Math.min(Math.floor(streak), 3) : 0;

  // Determine displayed rank robustly: support either 0-based or 1-based `index` props.
  const providedIndex = Number(index);
  const displayRank = Number.isFinite(Number(rank))
    ? rank
    : (Number.isFinite(providedIndex) ? (providedIndex >= 1 ? providedIndex : providedIndex + 1) : undefined);

  const slug = tickerFromSymbol(display).toLowerCase();
  const coinbaseUrl = `https://www.coinbase.com/price/${slug}`;

  const handleClick = (e) => {
    // if the user clicked on actions (star / info), don't navigate
    if (e.target.closest && e.target.closest('.tr-col-actions')) return;
    window.open(coinbaseUrl, '_blank', 'noopener');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleClick(e);
  };

  const isLoss = typeof explicitIsLoss === 'boolean' ? explicitIsLoss : pct < 0;

  return (
    <div
      className={`token-row token-row--clickable ${isLoss ? 'is-loss' : pct > 0 ? 'is-gain' : ''}`}
      data-row="token"
      role="link"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onClick={handleClick}
      onMouseEnter={onHover ? () => onHover(display, data) : undefined}
    >
      <div className="row-hover-bg" aria-hidden />
      <div className="row-base-line" aria-hidden />
      <div className="tr-col-rank">
        <div className={`rank-badge ${isLoss ? 'rank-badge-loss' : 'rank-badge-gain'}`}>{displayRank ?? 1}</div>
      </div>
      <div className="tr-symbol">
        {display}
        {sentiment ? (
          <span
            className="sentiment-dot"
            title={`FG ${sentiment?.fear_greed?.value ?? "?"}`}
            aria-label="Sentiment indicator"
          />
        ) : null}
        {/* streak indicator removed to reduce visual clutter; keep logic if we want to re-enable later */}
      </div>
      <div className="tr-col-price">
        <div className="tr-price-current">{formatPrice(price)}</div>
        {prevPrice != null && (
          <div className="tr-price-prev">{formatPrice(prevPrice)}</div>
        )}
      </div>
      <div className={`tr-col-pct ${pctClass}`}>{formatPct(pct)}</div>
      <div className="tr-col-actions">
        <RowActions symbol={display} price={price} onInfo={(t) => onInfo && onInfo(t)} />
      </div>
    </div>
  );
}

export default memo(TokenRow);
