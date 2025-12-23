import { useMemo } from "react";
import { useData } from "../hooks/useData";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";

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
  const abs = Math.abs(n);
  const decimals = abs < 0.1 ? 4 : abs < 1 ? 3 : 2;
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(decimals)}%`;
};

const normalizeSymbol = (value) => {
  if (!value) return "";
  return value.replace(/-usd$|-usdt$|-perp$/i, "").toUpperCase();
};

export function VolumeBannerScroll({ tokens = [] }) {
  const { volume1h } = useData();

  const rawItems = useMemo(() => {
    if (Array.isArray(tokens) && tokens.length) return tokens;
    if (Array.isArray(volume1h) && volume1h.length) return volume1h;
    return [];
  }, [tokens, volume1h]);

  const display = useMemo(() => {
    return rawItems
      .map((t) => {
        const symbol = normalizeSymbol(t?.symbol || t?.ticker);
        const volNow = Number(
          t?.volume_1h_now ??
            t?.volume_1h ??
            t?.volume_24h ??
            t?.volume ??
            0
        );
        const pctRaw =
          t?.volume_change_1h_pct ??
          t?.change_1h_volume ??
          t?.volume_change_pct ??
          t?.volume_change ??
          0;
        const pctNum = Number(pctRaw);
        return {
          ...t,
          symbol,
          volume_1h_now: Number.isFinite(volNow) ? volNow : 0,
          volume_change_1h_pct: Number.isFinite(pctNum) ? pctNum : 0,
        };
      })
      .filter((t) => t.symbol)
      .sort(
        (a, b) =>
          (Number(b.volume_change_1h_pct) || 0) -
          (Number(a.volume_change_1h_pct) || 0)
      )
      .slice(0, 25);
  }, [rawItems]);

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
    <div className="bh-banner bh-banner--bottom">
      <div className="bh-banner-wrap">
        <div className="bh-banner-track bh-banner-track--loop">
          {looped.map((t, idx) => {
            const pct = Number(t.volume_change_1h_pct ?? 0);
            const isPos = pct > 0;
            const stateClass = pct < 0 ? "is-loss" : pct > 0 ? "is-gain" : "is-flat";
            const url = coinbaseSpotUrl(t || {});
            const inner = (
              <>
                <span className="bh-banner-symbol">{t.symbol || "--"}</span>
                <span className="bh-banner-price">{formatVolume(t.volume_1h_now)} vol</span>
                <span
                  className={`bh-banner-change ${
                    isPos ? "bh-banner-change--pos" : "bh-banner-change--neg"
                  }`}
                >
                  {formatPct(t.volume_change_1h_pct)}
                </span>
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

export default VolumeBannerScroll;
