import { useMemo } from "react";
import { useDataFeed } from "../hooks/useDataFeed";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
const formatPrice = (val) => {
  const n = Number(val ?? 0);
  if (Number.isNaN(n)) return "$0.00";
  if (Math.abs(n) >= 1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(4)}`;
};

const classifyPct = (val) => {
  const n = Number(val ?? 0);
  if (!Number.isFinite(n)) {
    return { display: "0.00%", state: "flat", className: "bh-banner-change--flat" };
  }
  const rounded = parseFloat(n.toFixed(2));
  if (rounded === 0) return { display: "0.00%", state: "flat", className: "bh-banner-change--flat" };
  if (rounded > 0) return { display: `+${rounded.toFixed(2)}%`, state: "positive", className: "bh-banner-change--pos" };
  return { display: `${rounded.toFixed(2)}%`, state: "negative", className: "bh-banner-change--neg" };
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
        const changePct = t?.price_change_1h_pct ?? t?.change_1h_price ?? t?.pct_change_1h ?? t?.price_change_1h ?? t?.pct_change ?? 0;
        const pctNum = Number(changePct ?? 0);
        return { ...t, symbol, price_now: priceNow, price_change_1h_pct: Number.isFinite(pctNum) ? pctNum : 0 };
      })
      .filter((t) => t.symbol)
      .sort((a, b) => Math.abs(b.price_change_1h_pct || 0) - Math.abs(a.price_change_1h_pct || 0))
      .slice(0, 25);
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

  const setRabbitHover = (on) => (e) => {
    const item = e.currentTarget;
    const board = item.closest(".board-core");
    if (!board) return;

    if (on) {
      board.setAttribute("data-row-hover", "1");
      const r = item.getBoundingClientRect();
      const b = board.getBoundingClientRect();
      const x = ((r.left + r.width / 2 - b.left) / b.width) * 100;
      const y = ((r.top + r.height / 2 - b.top) / b.height) * 100;
      board.style.setProperty("--emit-x", `${x}%`);
      board.style.setProperty("--emit-y", `${y}%`);
    } else {
      board.removeAttribute("data-row-hover");
    }
  };

  return (
    <div className="bh-banner bh-banner--top">
      <div className="bh-banner-wrap">
        <div key="price-banner-track" className="bh-banner-track bh-banner-track--loop">
          {looped.map((t, idx) => {
            const pctInfo = classifyPct(t.price_change_1h_pct ?? 0);
            const stateClass = pctInfo.state === "negative" ? "is-loss" : pctInfo.state === "positive" ? "is-gain" : "is-flat";
            const url = coinbaseSpotUrl(t || {});
            if (!url) {
              return (
                <div
                  key={`${t.symbol}-${idx}`}
                  className={`bh-banner-item bh-banner-chip ${stateClass}`}
                  onPointerEnter={setRabbitHover(true)}
                  onPointerLeave={setRabbitHover(false)}
                >
                  <span className="bh-banner-symbol">{t.symbol || "--"}</span>
                  <span className="bh-banner-price">{formatPrice(t.price_now)}</span>
                  <span className={`bh-banner-change ${pctInfo.className}`}>{pctInfo.display}</span>
                </div>
              );
            }
            return (
              <a
                key={`${t.symbol}-${idx}`}
                className={`bh-banner-item bh-banner-chip ${stateClass}`}
                href={url}
                target="_blank"
                rel="noreferrer noopener"
                onPointerEnter={setRabbitHover(true)}
                onPointerLeave={setRabbitHover(false)}
              >
                <span className="bh-banner-symbol">{t.symbol || "--"}</span>
                <span className="bh-banner-price">{formatPrice(t.price_now)}</span>
                <span className={`bh-banner-change ${pctInfo.className}`}>{pctInfo.display}</span>
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
}
