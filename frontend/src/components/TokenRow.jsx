import RowActions from "./tables/RowActions.jsx";

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
  const pctDisplay = (() => {
    if (typeof changePct !== "number") return "—";
    const abs = Math.abs(changePct);
    const places = abs < 1 ? 3 : 2;
    return `${changePct.toFixed(places)}%`;
  })();

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
          <div className="tr-price-current">
            {price != null ? `$${Number(price).toFixed(3)}` : "—"}
          </div>
          <div className="tr-price-prev">
            {prevPrice != null ? `$${Number(prevPrice).toFixed(3)}` : ""}
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
        <RowActions symbol={String(symbol || "").replace("-USD", "")} priceNow={price} onInfo={onInfo} />
      </div>
    </div>
  );
}
