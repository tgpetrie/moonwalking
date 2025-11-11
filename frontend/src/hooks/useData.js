// src/hooks/useData.js
import useSWR from "swr";
import { fetchData } from "../api.js";

const KEY = "/data";

function cleanSymbol(s) {
  if (!s) return "";
  return s.replace(/-USD$/i, "");
}

function normalize1m(arr = []) {
  return arr.map((item, idx) => ({
    __raw: item,
    symbol: cleanSymbol(item.symbol),
    price: item.current_price ?? null,
    prevPrice: item.initial_price_1min ?? null,
    pct: item.price_change_percentage_1min ?? null,
    rank: item.rank ?? idx + 1,
  }));
}

function normalize3m(arr = []) {
  return arr.map((item, idx) => ({
    __raw: item,
    symbol: cleanSymbol(item.symbol),
    price: item.current_price ?? null,
    prevPrice: item.initial_price_3min ?? null,
    pct: item.price_change_percentage_3min ?? null,
    rank: item.rank ?? idx + 1,
  }));
}

export function useData() {
  const { data, error, mutate } = useSWR(KEY, () => fetchData(KEY), {
    revalidateOnFocus: true,
  });

  const inner = data && typeof data === "object" ? data.data : null;

  const gainers1m = inner?.gainers_1m ? normalize1m(inner.gainers_1m) : [];
  const gainers3m = inner?.gainers_3m ? normalize3m(inner.gainers_3m) : [];
  const losers3m = inner?.losers_3m ? normalize3m(inner.losers_3m) : [];
  const banner1h = Array.isArray(inner?.banner_1h) ? inner.banner_1h : [];

  const bySymbol = {};
  [...gainers1m, ...gainers3m, ...losers3m].forEach((row) => {
    if (row.symbol) bySymbol[row.symbol] = row;
  });

  return {
    data: {
      gainers1m: { rows: gainers1m, loading: false },
      gainers3m: { rows: gainers3m, loading: false },
      losers3m: { rows: losers3m, loading: false },
      banner1h,
    },
    bySymbol,
    isLoading: !data && !error,
    isError: !!error,
    mutate,
  };
}
