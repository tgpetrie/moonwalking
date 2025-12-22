import { useMemo } from "react";
import { useDataFeed } from "../hooks/useDataFeed";
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

        const volNowRaw = t?.volume_1h_now ?? t?.volume_1h ?? t?.volume_24h ?? 0;
        const volNow = Number(volNowRaw);

        const changePctRaw =
          t?.volume_change_1h_pct ??
          t?.change_1h_volume ??
          t?.volume_1h_pct ??
          t?.volume_change_pct;

        const pctFromBackend = Number(changePctRaw);

        // Optional "ago" keys for fallback computation
        const volAgoRaw =
          t?.volume_1h_ago ??
          t?.volume_1h_prev ??
          t?.volume_prev_1h ??
          t?.volume_then_1h ??
          t?.volume_prior_1h;

        const volAgo = Number(volAgoRaw);

        let computedPct = NaN;
        if (Number.isFinite(volNow) && Number.isFinite(volAgo) && volAgo > 0) {
          computedPct = ((volNow - volAgo) / volAgo) * 100;
        }

        const volume_change_1h_pct =
          Number.isFinite(pctFromBackend) && pctFromBackend !== 0 ? pctFromBackend :
          Number.isFinite(computedPct) ? computedPct : 0;

        return {
          ...t,
          symbol,
          volume_1h_now: Number.isFinite(volNow) ? volNow : 0,
          volume_change_1h_pct,
        };
      })
      // Backend sometimes ships volume values without a computed % change (all zeros).
      // Still render the banner so the UI doesn't go quiet.
      .filter((t) => t.symbol)
      .sort((a, b) => {
        // Sort by absolute % change if available, otherwise by volume
        const aPct = Math.abs(a.volume_change_1h_pct || 0);
        const bPct = Math.abs(b.volume_change_1h_pct || 0);
        if (aPct > 0 || bPct > 0) {
          return bPct - aPct;
        }
        // Fallback: sort by volume if no % change
        return (b.volume_1h_now || 0) - (a.volume_1h_now || 0);
      })
      .slice(0, 25);
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
        <div key="volume-banner-track" className="bh-banner-track bh-banner-track--loop">
          {looped.map((t, idx) => {
            const pct = Number(t.volume_change_1h_pct ?? 0);
            const isPos = pct > 0;
            const stateClass = pct < 0 ? "is-loss" : pct > 0 ? "is-gain" : "is-flat";
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
                  <span className="bh-banner-price">{formatVolume(t.volume_1h_now)} vol</span>
                  <span className={`bh-banner-change ${isPos ? "bh-banner-change--pos" : "bh-banner-change--neg"}`}>{formatPct(t.volume_change_1h_pct)}</span>
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
                <span className="bh-banner-price">{formatVolume(t.volume_1h_now)} vol</span>
                <span className={`bh-banner-change ${isPos ? "bh-banner-change--pos" : "bh-banner-change--neg"}`}>{formatPct(t.volume_change_1h_pct)}</span>
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default VolumeBannerScroll;
