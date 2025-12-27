import { useMemo } from "react";
import { useData } from "../hooks/useData";
import { coinbaseSpotUrl } from "../utils/coinbaseUrl";
import { useBannerLensMarquee } from "../hooks/useBannerLensMarquee";

const formatVolume = (val) => {
  const n = Number(val ?? 0);
  if (!Number.isFinite(n)) return "0";
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(0);
};

const formatPct = (val) => {
  if (val == null) return "—";
  const n = Number(val);
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  const decimals = abs < 0.1 ? 4 : abs < 1 ? 3 : 2;
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(decimals)}%`;
};

const normalizeSymbol = (value) => {
  if (!value) return "";
  return value.replace(/-usd$|-usdt$|-perp$/i, "").toUpperCase();
};

export function VolumeBannerScroll({ tokens = [], loading = false }) {
  const { volume1h } = useData();
  const MIN_BASELINE = 100;
  const { wrapRef, trackRef } = useBannerLensMarquee(42, [tokens?.length, volume1h?.length]);

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
        const prev = Number(
          t?.volume_1h_prev ??
            t?.volume_prev ??
            t?.volume_prev_1h ??
            t?.volume_1h_ago ??
            null
        );
        const hasBaseline = Number.isFinite(prev) && prev >= MIN_BASELINE;
        return {
          ...t,
          symbol,
          volume_1h_now: Number.isFinite(volNow) ? volNow : 0,
          volume_change_1h_pct: Number.isFinite(pctNum) ? pctNum : null,
          volume_baseline_ok: hasBaseline,
        };
      })
      .filter((t) => t.symbol && t.volume_change_1h_pct != null)
      .sort(
        (a, b) => {
          if (a.volume_baseline_ok !== b.volume_baseline_ok) {
            return a.volume_baseline_ok ? -1 : 1;
          }
          return (Number(b.volume_change_1h_pct) || 0) - (Number(a.volume_change_1h_pct) || 0);
        }
      )
      .slice(0, 25);
  }, [rawItems]);

  const looped = display.length ? [...display, ...display] : [];
  if (!looped.length) {
    const emptyCopy = loading ? "Warming up volume feed…" : "No 1h volume activity yet.";
    return (
      <div className="bh-banner bh-banner--bottom">
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
    <div className="bh-banner bh-banner--bottom">
      <div className="bh-banner-wrap" ref={wrapRef}>
        <div className="bh-banner-track bh-banner-track--manual" ref={trackRef}>
          {looped.map((t, idx) => {
            const pct = t.volume_baseline_ok ? Number(t.volume_change_1h_pct ?? 0) : null;
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
                  {formatPct(pct)}
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
