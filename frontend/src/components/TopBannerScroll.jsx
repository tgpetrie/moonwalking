import { useMemo } from "react";
import { useDataFeed } from "../hooks/useDataFeed";

const formatPrice = (val) => {
  const n = Number(val ?? 0);
  if (Number.isNaN(n)) return "$0.00";
  if (Math.abs(n) >= 1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(4)}`;
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

export default function TopBannerScroll({ rows = [], items = [], tokens = [] }) {
  const { data } = useDataFeed();

  const feedRows = useMemo(() => {
    const list = data?.banner_1h_price || data?.banner_1h || data?.banner_price_1h;
    if (Array.isArray(list)) return list;
    if (list && Array.isArray(list.data)) return list.data;
    return [];
  }, [data]);

  const rawItems = useMemo(() => {
    if (Array.isArray(tokens) && tokens.length) return tokens;
    if (Array.isArray(rows) && rows.length) return rows;
    if (rows && Array.isArray(rows.data)) return rows.data;
    if (Array.isArray(items) && items.length) return items;
    if (items && Array.isArray(items.data)) return items.data;
    if (feedRows.length) return feedRows;
    return [];
  }, [tokens, rows, items, feedRows]);

  const normalized = useMemo(() => {
    return rawItems
      .map((t) => {
        const symbol = normalizeSymbol(t?.symbol || t?.ticker);
        const priceNow = t?.price_now ?? t?.current_price ?? t?.price;
        const changePct =
          t?.price_change_1h_pct ??
          t?.change_1h_price ??
          t?.pct_change_1h ??
          t?.price_change_1h ??
          t?.pct_change ??
          0;
        const pctNum = Number(changePct ?? 0);

        return {
          ...t,
          symbol,
          price_now: priceNow,
          price_change_1h_pct: Number.isFinite(pctNum) ? pctNum : 0,
        };
      })
      .filter((t) => t.symbol && t.price_change_1h_pct !== 0)
      .sort((a, b) => b.price_change_1h_pct - a.price_change_1h_pct)
      .slice(0, 24);
  }, [rawItems]);

  const display = normalized.length ? normalized : [];
  const looped = display.length ? [...display, ...display] : [];

  if (!looped.length) {
    return (
      <div className="bh-banner bh-banner--top">
        <div className="bh-banner-wrap">
          <div className="bh-banner-track">
            <span className="bh-banner-empty">No 1h price movers yet.</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bh-banner bh-banner--top">
      <div className="bh-banner-wrap">
        <div className="bh-banner-track">
          {looped.map((t, idx) => {
            const isPos = (t.price_change_1h_pct ?? 0) >= 0;
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
                <span className="bh-banner-price">{formatPrice(t.price_now)}</span>
                <span className={`bh-banner-change ${isPos ? "bh-banner-change--pos" : "bh-banner-change--neg"}`}>
                  {formatPct(t.price_change_1h_pct)}
                </span>
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
}
