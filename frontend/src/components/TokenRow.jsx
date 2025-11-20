import React, { memo } from "react";
import { useSentiment } from "../context/SentimentContext.jsx";
import { formatPrice, formatPct, tickerFromSymbol } from "../utils/format.js";
import RowActions from "./tables/RowActions.jsx";

// TokenRow: BHABIT-styled token row used by 1m/3m movers panels.
function TokenRow({
  row,
  token,
  item,
  // explicit prop fallbacks for older callsites
  symbol,
  currentPrice,
  previousPrice,
  changePct,
  priceChange1min,
  priceChange3min,
  index = 0,
  rank,
  rowType,
  changeKey,
  interval = "3m",
  onInfo,
  onHover,
  isLoss: explicitIsLoss,
} = {}) {
  // Support multiple calling conventions: row / token / item OR explicit primitive props
  const raw = row || token || item || {};
  const explicit = {};
  if (symbol) explicit.symbol = symbol;
  if (currentPrice !== undefined) explicit.current_price = currentPrice;
  if (previousPrice !== undefined) explicit.previous_price = previousPrice;
  if (changePct !== undefined) explicit.price_change_percentage_3min = changePct;
  if (priceChange1min !== undefined) explicit.price_change_percentage_1min = priceChange1min;
  if (priceChange3min !== undefined) explicit.price_change_percentage_3min = priceChange3min;
  const data = Object.keys(raw).length ? raw : explicit;
  const rawSymbol = data.symbol || data.ticker || "";
  const display = rawSymbol?.replace(/-(USD|USDT|PERP)$/i, "") || rawSymbol || "--";

  const price =
    data.current_price ??
    data.price ??
    data.last_price ??
    data.latest_price ??
    null;

  const prevPrice =
    data.previous_price ??
    data.initial_price_1min ??
    data.initial_price_3min ??
    data.price_1m_ago ??
    data.price_3m_ago ??
    data.start_price ??
    data.open_price ??
    data.open_price_1m ??
    data.open_price_3m ??
    data.snapshot_price ??
    null;

  const pctRaw = changeKey
    ? data?.[changeKey]
    : (data.pct ??
      data._pct ??
      data.price_change_percentage_1min ??
      data.price_change_1m ??
      data.price_change_percentage_3min ??
      data.price_change_1h ??
      data.changePercent ??
      0);

  const pctNum = Number(pctRaw);
  const pct = Number.isFinite(pctNum) ? pctNum : 0;


  // If backend didn't provide an explicit previous price but we have a
  // current price and a percent change, derive the implied starting price:
  //   pct = (current - prev) / prev * 100  =>  prev = current / (1 + pct/100)
  let effectivePrevPrice = prevPrice;
  if (effectivePrevPrice == null && price != null && Number.isFinite(pct) && pct !== 0) {
    const denom = 1 + pct / 100;
    if (denom !== 0) {
      effectivePrevPrice = price / denom;
    }
  }

  const { sentiment } = useSentiment() || {};

  // Determine visual gain/loss styling: prefer explicit rowType, then explicitIsLoss, then sign.
  let rowKindClass = "";
  if (rowType === "gainer") rowKindClass = "is-gain";
  else if (rowType === "loser") rowKindClass = "is-loss";
  else if (typeof explicitIsLoss === "boolean")
    rowKindClass = explicitIsLoss ? "is-loss" : "is-gain";
  else rowKindClass = pct >= 0 ? "is-gain" : "is-loss";

  const signClass = rowKindClass; // "is-gain" / "is-loss"

  const pctClass = pct < 0 ? "token-pct-loss" : "token-pct-gain";
  const streakRaw = data.trendStreak ?? data.trend_streak ?? data.peak_count ?? 0;
  const streak = Number.isFinite(Number(streakRaw)) ? Number(streakRaw) : 0;
  // Cap visible streak dots to avoid inflated counts; tooltip contains raw value.
  const streakDots = streak >= 1 ? Math.min(Math.floor(streak), 3) : 0;

  // Determine displayed rank robustly: prefer 1‑based ranks; treat 0/NaN as "unset".
  const providedIndex = Number(index);
  const numericRank = Number(rank);
  let displayRank;
  if (Number.isFinite(numericRank) && numericRank >= 1) {
    displayRank = numericRank;
  } else if (Number.isFinite(providedIndex)) {
    displayRank = providedIndex >= 1 ? providedIndex : providedIndex + 1;
  } else {
    displayRank = undefined;
  }

  const slug = tickerFromSymbol(display).toLowerCase();
  const pair = slug.endsWith("-usd") ? slug : `${slug}-usd`;
  const coinbaseUrl = `https://www.coinbase.com/advanced-trade/spot/${pair}`;

  const handleClick = (e) => {
    // if the user clicked on actions (star / info), don't navigate
    if (e.target.closest && e.target.closest(".tr-col-actions")) return;
    window.open(coinbaseUrl, "_blank", "noopener");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleClick(e);
  };

  return (
    <div
      className={`token-row table-row ${signClass}`}
      data-row="token"
      role="link"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onClick={handleClick}
      onMouseEnter={onHover ? () => onHover(display, data) : undefined}
    >
      {/* hover glow handled via CSS ::after to create an inner-fill under the row;
        keep DOM minimal so pseudo-elements can be positioned reliably */}
      <div className="tr-col tr-col-rank">
        <div className={`rank-badge tr-rank-badge ${rowKindClass === "is-loss" ? "rank-badge-loss" : "rank-badge-gain"}`}>
          {displayRank ?? 1}
        </div>
      </div>
      <div className="tr-col tr-col-symbol tr-symbol">
        <span>{display}</span>
        {sentiment ? (
          <span
            className="sentiment-dot"
            title={`FG ${sentiment?.fear_greed?.value ?? "?"}`}
            aria-label="Sentiment indicator"
          />
        ) : null}
        {/* streak indicator removed to reduce visual clutter; keep logic if we want to re-enable later */}
      </div>
      <div className="tr-col tr-col-price">
        <div className="tr-price-current">
          {price != null ? formatPrice(price) : "—"}
        </div>
        <div
          className={`tr-price-prev ${effectivePrevPrice == null ? "tr-price-prev--empty" : ""}`}
          aria-hidden={effectivePrevPrice == null}
        >
          {effectivePrevPrice != null ? formatPrice(effectivePrevPrice) : "—"}
        </div>
      </div>
      <div className="tr-col tr-col-pct">
        <span className={`tr-pct ${pctClass}`}>{formatPct(pct)}</span>
      </div>
      <div className="tr-col tr-col-actions">
        <RowActions
          symbol={display}
          price={price}
          onInfo={(t) => onInfo && onInfo(t)}
        />
      </div>
    </div>
  );
}

export default memo(TokenRow);
