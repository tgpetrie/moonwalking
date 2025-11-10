import RowActions from "./tables/RowActions.jsx";
import { formatPrice, formatPct } from "../lib/format.js";

export default function TokenRow({
  index,
  symbol,
  price,
  prevPrice,
  changePct,
  side = "up",
  onInfo,
}) {
  const pctClass =
    side === "down" ? "token-pct token-pct-loss" : "token-pct token-pct-gain";
  const pctDisplay = formatPct(changePct);

  return (
    <div className={`token-row ${index === 1 ? "token-row--top" : ""}`} tabIndex={0}>
      {/* rank */}
      <div className="tr-col tr-col-rank">
        <div className="tr-rank">{index}</div>
      </div>

      {/* symbol */}
      <div className="tr-col tr-col-symbol">
        <div className="tr-symbol">{symbol?.replace("-USD", "")}</div>
      </div>

      {/* line / price block */}
      <div className="tr-col tr-col-price">
        <div className="tr-line" />
        <div className="tr-price-block">
        <div className="tr-price-current">{formatPrice(price)}</div>
          <div className="tr-price-prev">
            {prevPrice != null ? formatPrice(prevPrice) : ""}
          </div>
        </div>
      </div>

      {/* pct */}
      <div
        className="tr-col tr-col-pct clickable"
        onClick={() =>
          onInfo &&
          onInfo({
            symbol: String(symbol || "").replace("-USD", ""),
            price,
            prevPrice,
            changePct,
          })
        }
      >
        <div className={pctClass}>{pctDisplay}</div>
      </div>

      {/* actions */}
      <div className="tr-col tr-col-actions">
        <RowActions symbol={String(symbol || "").replace("-USD", "")} price={price} onInfo={onInfo} />
      </div>
    </div>
  );
}
