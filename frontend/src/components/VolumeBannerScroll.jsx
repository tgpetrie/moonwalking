import { useMemo } from "react";
import { useDataFeed } from "../hooks/useDataFeed";

const formatVolume = (val) => {
  const n = Number(val ?? 0);
  if (!Number.isFinite(n)) return "0";
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(0);
};

const formatPct = (val) => {
  const n = Number(val ?? 0);
  if (!Number.isFinite(n)) return "0.00%";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
};

const normalizeSymbol = (value) => {
  if (!value) return "";
  return value.replace(/-USD$|-USDT$|-PERP$/i, "").toUpperCase();
};

export function VolumeBannerScroll({ tokens: tokensProp }) {
  const { data } = useDataFeed();

  const rawItems = useMemo(() => {
    const list = tokensProp?.length ? tokensProp : data?.banner_1h_volume || data?.banner_volume_1h || [];
    if (Array.isArray(list)) return list;
    if (list && Array.isArray(list.data)) return list.data;
    return [];
  }, [tokensProp, data]);

  const normalized = useMemo(() => {
    return rawItems
      .map((t) => {
        const symbol = normalizeSymbol(t?.symbol || t?.ticker);
        const volNow = t?.volume_1h_now ?? t?.volume_24h ?? t?.volume_1h ?? 0;
        const changePct =
          t?.volume_change_1h_pct ??
          t?.change_1h_volume ??
          t?.volume_1h_pct ??
          t?.volume_change_pct ??
          0;
        const pctNum = Number(changePct ?? 0);

        return {
          ...t,
          symbol,
          volume_1h_now: Number.isFinite(Number(volNow)) ? volNow : 0,
          volume_change_1h_pct: Number.isFinite(pctNum) ? pctNum : 0,
        };
      })
      .filter((t) => t.symbol)
      .sort((a, b) => b.volume_change_1h_pct - a.volume_change_1h_pct)
      .slice(0, 24);
  }, [rawItems]);

  const display = normalized.length ? normalized : [];
  const looped = display.length ? [...display, ...display] : [];

  if (!looped.length) {
    return (
      <div className="bh-banner bh-banner--bottom">
        <div className="bh-banner-wrap">
          <div className="bh-banner-track">
            <span className="bh-banner-empty">No 1h volume activity yet.</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bh-banner bh-banner--bottom">
      <div className="bh-banner-wrap">
        <div className="bh-banner-track">
          {looped.map((t, idx) => {
            const changeVal = Number(t.volume_change_1h_pct ?? 0);
            const rounded = Number(changeVal.toFixed(2));
            let deltaClass = "bh-banner-change--flat";
            let prefix = "";
            if (rounded > 0) {
              deltaClass = "bh-banner-change--pos";
              prefix = "+";
            } else if (rounded < 0) {
              deltaClass = "bh-banner-change--neg";
            }
            const pair = t.symbol ? `${t.symbol}-USD` : "";
            return (
              <a
                key={`${t.symbol}-${idx}`}
                className="bh-banner-item"
                href={t.symbol ? `https://www.coinbase.com/advanced-trade/spot/${pair}` : "#"}
                target="_blank"
                rel="noreferrer"
              >
                <span className="bh-banner-symbol">{t.symbol || "--"}</span>
                <span className="bh-banner-price">{formatVolume(t.volume_1h_now)} vol</span>
                <span className={`bh-banner-change ${deltaClass}`}>
                  {`${prefix}${rounded.toFixed(2)}%`}
                </span>
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default VolumeBannerScroll;
