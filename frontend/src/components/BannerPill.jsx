export function BannerPill({ symbol, metric, changePct, positive }) {
  return (
    <div className="banner-pill">
      <span className="banner-symbol">{symbol}</span>
      <span className="banner-metric">{metric}</span>
      <span className={`banner-change ${positive ? "pos" : "neg"}`}>
        {Number(changePct).toFixed(2)}%
      </span>
    </div>
  );
}

export default BannerPill;
