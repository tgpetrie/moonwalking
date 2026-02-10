// frontend/src/hooks/useDashboardData.js
import { useEffect, useRef } from "react";
import { useData } from "../context/DataContext";

const LS_KEY = "bh_last_payload_v1";

function writeLastPayload(value) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(value));
  } catch {}
}

// map raw backend row to UI row while preserving ALL backend fields
function mapRowWithInitial(x = {}) {
  // normalize symbol display
  const symbol = String(x.ticker ?? x.symbol ?? "").toUpperCase();
  const displaySymbol = symbol.replace(/-(USD|USDT|PERP)$/i, "");

  // Map backend field names to UI field names
  const change_3m = x.change_3m ?? x.price_change_percentage_3min ?? undefined;
  const change_1m = x.change_1m ?? x.price_change_percentage_1min ?? undefined;

  // Return the ORIGINAL object with symbol normalization + field mapping
  return {
    ...x, // preserve ALL backend fields
    symbol: displaySymbol,
    change_3m,
    change_1m,
  };
}

function toNum(value) {
  if (value == null) return null;
  if (typeof value === "string") {
    const cleaned = value.replace(/[%+,]/g, "").trim();
    if (!cleaned) return null;
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : null;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function pick1hChange(row) {
  if (!row) return null;
  return (
    toNum(row.price_change_percentage_1h) ??
    toNum(row.price_change_1h) ??
    toNum(row.change_1h) ??
    toNum(row.pct_change_1h) ??
    toNum(row.pct_1h) ??
    toNum(row.change_1h_price) ??
    toNum(row.delta_1h) ??
    toNum(row.pct_change) ??
    null
  );
}

export function useDashboardData() {
  const { data, error, loading, oneMinRows, threeMin, banners, alerts, heartbeatPulse, lastFetchTs, warming, warming3m, staleSeconds, partial, lastGoodTs, activeAlerts, alertsRecent, alertsMeta } = useData();

  const payload = data || {};
  const alertsList = Array.isArray(alerts) && alerts.length ? alerts : Array.isArray(payload.alerts) ? payload.alerts : [];

  const lastGood1mRef = useRef([]);
  const lastGood3mGRef = useRef([]);
  const lastGood3mLRef = useRef([]);
  const lastGoodBpRef = useRef([]);
  const lastGoodBvRef = useRef([]);

  // Use the granular slices from DataContext (which have independent publish cadences)
  const g1 = Array.isArray(oneMinRows) && oneMinRows.length > 0 ? oneMinRows : Array.isArray(payload.gainers_1m) ? payload.gainers_1m : [];
  const g3 = Array.isArray(threeMin?.gainers) && threeMin.gainers.length > 0 ? threeMin.gainers : Array.isArray(payload.gainers_3m) ? payload.gainers_3m : [];
  const l3 = Array.isArray(threeMin?.losers) && threeMin.losers.length > 0 ? threeMin.losers : Array.isArray(payload.losers_3m) ? payload.losers_3m : [];
  const bv = Array.isArray(banners?.volume) && banners.volume.length > 0 ? banners.volume : Array.isArray(payload.banner_1h_volume) ? payload.banner_1h_volume : [];
  const bp = Array.isArray(banners?.price) && banners.price.length > 0 ? banners.price : Array.isArray(payload.banner_1h_price) ? payload.banner_1h_price : [];
  const v1hRaw = Array.isArray(payload.volume1h) ? payload.volume1h : [];

  useEffect(() => {
    if (Array.isArray(g1) && g1.length) lastGood1mRef.current = g1;
  }, [g1]);

  useEffect(() => {
    if (Array.isArray(g3) && g3.length) lastGood3mGRef.current = g3;
  }, [g3]);

  useEffect(() => {
    if (Array.isArray(l3) && l3.length) lastGood3mLRef.current = l3;
  }, [l3]);

  useEffect(() => {
    if (Array.isArray(bp) && bp.length) lastGoodBpRef.current = bp;
  }, [bp]);

  useEffect(() => {
    if (Array.isArray(bv) && bv.length) lastGoodBvRef.current = bv;
  }, [bv]);

  const g1Safe = g1.length ? g1 : lastGood1mRef.current;
  const g3Safe = g3.length ? g3 : lastGood3mGRef.current;
  const l3Safe = l3.length ? l3 : lastGood3mLRef.current;
  const bpSafe = bp.length ? bp : lastGoodBpRef.current;
  const bvSafe = bv.length ? bv : lastGoodBvRef.current;

  const gainers1m = g1Safe.map(mapRowWithInitial);
  const gainers3m = g3Safe.map(mapRowWithInitial);
  const losers3m = l3Safe.map(mapRowWithInitial);
  const bannerPrice1h = bpSafe
    .map(mapRowWithInitial)
    .map((row) => {
      const change1h = pick1hChange(row);
      return { ...row, change_1h: row.change_1h ?? change1h, _change_1h: change1h };
    })
    .filter((row) => Number.isFinite(row._change_1h))
    .sort((a, b) => b._change_1h - a._change_1h)
    .map((row, idx) => {
      const { _change_1h, ...rest } = row;
      return { ...rest, rank: idx + 1 };
    });
  const volume1h = v1hRaw.map(mapRowWithInitial);
  const bannerVolume1h = bvSafe.map(mapRowWithInitial);
  const finalVolume1h = volume1h.length ? volume1h : bannerVolume1h;

  // build a quick symbol → current price map for watchlist reconciliation
  const priceMap = {};
  for (const r of [...gainers1m, ...gainers3m, ...losers3m]) {
    if (r && r.symbol) priceMap[r.symbol] = r.price;
  }

  // Persist last good payload for instant reloads
  const prevDataRef = useRef(null);
  useEffect(() => {
    if (!data || error) return;
    if (prevDataRef.current !== data) {
      prevDataRef.current = data;
      writeLastPayload(data);
    }
  }, [data, error]);

  // Last updated timestamp
  const lastUpdatedTsRef = useRef(null);
  useEffect(() => {
    if (!data || error) return;
    if (prevDataRef.current !== data) {
      lastUpdatedTsRef.current = Date.now();
    }
  }, [data, error]);

  const lastUpdatedTs = lastUpdatedTsRef.current;
  const lastUpdated = lastUpdatedTs ? new Date(lastUpdatedTs) : null;

  // Extract error/coverage metadata from payload
  const errors = payload.errors || {};
  const coverage = payload.coverage || {};
  const fatal = errors?.fatal || null;

  return {
    raw: data,
    alerts: alertsList,
    gainers1m,
    gainers3m,
    losers3m,
    bannerVolume1h,
    bannerPrice1h,
    volume1h: finalVolume1h,
    priceMap,
    errors,
    coverage,
    fatal,
    loading,
    isLoading: loading,
    isValidating: false, // No longer using SWR validation
    error,
    mutate: null, // No longer using SWR mutate
    lastUpdatedTs,
    lastUpdated,
    heartbeatPulse,
    lastFetchTs,
    warming,
    warming3m,
    staleSeconds,
    partial,
    lastGoodTs,
    activeAlerts: activeAlerts || [],
    alertsRecent: alertsRecent || [],
    alertsMeta: alertsMeta || {},
  };
}
