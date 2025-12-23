import { useMemo } from "react";
import { useDataFeed } from "./useDataFeed";

const normalizeTicker = (value) => {
  if (!value) return "";
  return String(value).replace(/-USD$|-USDT$|-PERP$/i, "").toUpperCase();
};

const withDisplaySymbol = (row) => {
  const symbol = row?.symbol || row?.ticker || "";
  return { ...row, symbol, displaySymbol: normalizeTicker(symbol) };
};

const computeDeltaPct = (baseline, current) => {
  const b = Number(baseline);
  const c = Number(current);
  if (!Number.isFinite(b) || !Number.isFinite(c) || b === 0) return null;
  return ((c - b) / b) * 100;
};

export function useData() {
  const { data, error, isLoading, mutate } = useDataFeed();
  const payload = data?.data ?? data ?? {};
  const meta = payload.meta ?? data?.meta ?? {};

  const view = useMemo(() => {
    const banner1hRaw = payload.banner_1h_price ?? payload.banner1h ?? [];
    const volume1hRaw = payload.banner_1h_volume ?? payload.volume1h ?? [];
    const gainers1mRaw = payload.gainers_1m ?? [];
    const gainers3mRaw = payload.gainers_3m ?? [];
    const losers3mRaw = payload.losers_3m ?? [];
    const watchlistRaw = payload.watchlist ?? undefined;

    const banner1h = Array.isArray(banner1hRaw) ? banner1hRaw.map(withDisplaySymbol) : [];
    const volume1h = Array.isArray(volume1hRaw) ? volume1hRaw.map(withDisplaySymbol) : [];
    const gainers_1m = Array.isArray(gainers1mRaw) ? gainers1mRaw.map(withDisplaySymbol) : [];
    const gainers_3m = Array.isArray(gainers3mRaw) ? gainers3mRaw.map(withDisplaySymbol) : [];
    const losers_3m = Array.isArray(losers3mRaw) ? losers3mRaw.map(withDisplaySymbol) : [];

    const watchlist = Array.isArray(watchlistRaw)
      ? watchlistRaw.map((w) => {
          const symbol = w?.symbol || "";
          const baseline = w?.baseline;
          const current = w?.current;
          const deltaPct = computeDeltaPct(baseline, current);
          return {
            ...w,
            symbol,
            displaySymbol: normalizeTicker(symbol),
            deltaPct,
          };
        })
      : undefined;

    return {
      banner1h,
      volume1h,
      gainers_1m,
      gainers_3m,
      losers_3m,
      watchlist,
    };
  }, [payload]);

  const gainers1m = payload.gainers_1m ?? [];
  const gainers3m = payload.gainers_3m ?? [];
  const losers3m = payload.losers_3m ?? [];
  const banner1hPrice = payload.banner_1h_price ?? [];
  const banner1hVolume = payload.banner_1h_volume ?? [];
  const latestBySymbol = {};
  const push = (r) => {
    if (r && r.symbol) latestBySymbol[String(r.symbol).toUpperCase()] = r;
  };
  [...gainers1m, ...gainers3m, ...losers3m, ...banner1hPrice, ...banner1hVolume].forEach(push);

  return {
    ...view,
    gainers1m,
    gainers3m,
    losers3m,
    banner1hPrice,
    banner1hVolume,
    latestBySymbol,
    data: payload,
    meta: {
      ...meta,
      last_updated: payload.updated_at || meta.last_updated,
    },
    loading: isLoading,
    error,
    mutate,
    updated_at: payload.updated_at ?? data?.updated_at,
  };
}

export default useData;
