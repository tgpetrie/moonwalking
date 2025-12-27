import { useMemo } from "react";
import { useData } from "../hooks/useData";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { useBannerLensMarquee } from "../hooks/useBannerLensMarquee";

const formatPrice = (val) => {
  const n = Number(val ?? 0);
  if (Number.isNaN(n)) return "$0.00";
  if (Math.abs(n) >= 1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(4)}`;
};

const classifyPct = (val) => {
  const n = Number(val ?? 0);
  if (!Number.isFinite(n)) {
    return { display: "0.00%", className: "bh-banner-change--flat" };
  }

  const abs = Math.abs(n);
  const decimals = abs < 0.1 ? 4 : abs < 1 ? 3 : 2;
  const rounded = parseFloat(n.toFixed(decimals));

  if (rounded === 0) {
    return { display: `0.${"0".repeat(decimals)}%`, className: "bh-banner-change--flat" };
  }

  if (rounded > 0) {
    return {
      display: `+${rounded.toFixed(decimals)}%`,
      className: "bh-banner-change--pos",
    };
  }

  return {
    display: `${rounded.toFixed(decimals)}%`,
    className: "bh-banner-change--neg",
  };
};

const normalizeSymbol = (value) => {
  if (!value) return "";
  return value.replace(/-usd$|-usdt$|-perp$/i, "").toUpperCase();
};

export function TopBannerScroll({ tokens = [], rows = [], items = [], loading = false }) {
  const { banner1h } = useData();
  const { wrapRef, trackRef } = useBannerLensMarquee(42, [tokens?.length, rows?.length, items?.length, banner1h?.length]);

  const rawItems = useMemo(() => {
    if (Array.isArray(tokens) && tokens.length) return tokens;
    if (Array.isArray(rows) && rows.length) return rows;
    if (Array.isArray(items) && items.length) return items;
    if (Array.isArray(banner1h) && banner1h.length) return banner1h;
    return [];
  }, [tokens, rows, items, banner1h]);

  const normalized = useMemo(() => {
    return rawItems
      .map((t) => {
        const symbol = normalizeSymbol(t?.symbol || t?.ticker);
        const priceNow = Number(
          t?.price_now ?? t?.current_price ?? t?.price ?? 0
        );
        const pctRaw =
          t?.price_change_1h_pct ??
          t?.change_1h_price ??
          t?.pchange_1h ??
          t?.price_change ??
          0;
        const pctNum = Number(pctRaw);
        return {
          ...t,
          symbol,
          price_now: Number.isFinite(priceNow) ? priceNow : 0,
          price_change_1h_pct: Number.isFinite(pctNum) ? pctNum : 0,
        };
      })
      .filter((t) => t.symbol)
      .sort(
        (a, b) =>
          (Number(b.price_change_1h_pct) || 0) -
          (Number(a.price_change_1h_pct) || 0)
      )
      .slice(0, 25);
  }, [rawItems]);

  const display = normalized.length ? normalized : [];
  const looped = display.length ? [...display, ...display] : [];

  if (!looped.length) {
    const emptyCopy = loading ? "Warming up market feed…" : "No 1h price movers yet.";
    return (
      <div className="bh-banner bh-banner--top">
        <div className="bh-banner-wrap">
          <div className="bh-banner-track">
            <span className="bh-banner-empty">{emptyCopy}</span>
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
      <div className="bh-banner-wrap" ref={wrapRef}>
        <div className="bh-banner-track bh-banner-track--manual" ref={trackRef}>
          {looped.map((t, idx) => {
            const pctInfo = classifyPct(t.price_change_1h_pct);
            const stateClass = pctInfo.className.replace("bh-banner-change--", "is-");
            const url = coinbaseSpotUrl(t || {});
            const inner = (
              <>
                <span className="bh-banner-symbol">{t.symbol || "--"}</span>
                <span className="bh-banner-price">{formatPrice(t.price_now)}</span>
                <span className={`bh-banner-change ${pctInfo.className}`}>{pctInfo.display}</span>
              </>
            );

            if (!url) {
              return (
                <div
                  key={`${t.symbol}-${idx}`}
                  className={`bh-banner-item bh-banner-chip ${stateClass}`}
                  onPointerEnter={setRabbitHover(true)}
                  onPointerLeave={setRabbitHover(false)}
                >
                  {inner}
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
                {inner}
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default TopBannerScroll;
