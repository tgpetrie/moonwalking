import { useCallback, useEffect, useRef, useState } from "react";
import { fetchAllData } from "../api";

export function useDataFeed() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isValidating, setIsValidating] = useState(false);

  const last3mRef = useRef(0);
  const lastBannersRef = useRef(0);
  const cacheRef = useRef({ three: null, banners: null });
  const aliveRef = useRef(true);

  const fetchOnce = useCallback(async () => {
    if (!aliveRef.current) return null;
    setIsValidating(true);
    try {
      const json = await fetchAllData();
      if (!aliveRef.current) return null;

      const now = Date.now();
      const next = { ...json };

      if (now - last3mRef.current >= 30_000 || !cacheRef.current.three) {
        cacheRef.current.three = {
          gainers_3m: json?.gainers_3m || [],
          losers_3m: json?.losers_3m || [],
        };
        last3mRef.current = now;
      } else {
        next.gainers_3m = cacheRef.current.three.gainers_3m;
        next.losers_3m = cacheRef.current.three.losers_3m;
      }

      if (now - lastBannersRef.current >= 120_000 || !cacheRef.current.banners) {
        cacheRef.current.banners = {
          banner_1h_price: json?.banner_1h_price || [],
          banner_1h_volume: json?.banner_1h_volume || [],
        };
        lastBannersRef.current = now;
      } else {
        next.banner_1h_price = cacheRef.current.banners.banner_1h_price;
        next.banner_1h_volume = cacheRef.current.banners.banner_1h_volume;
      }

      setData(next);
      setError(null);
      return next;
    } catch (err) {
      if (!aliveRef.current) return null;
      setError(err);
      return null;
    } finally {
      if (!aliveRef.current) return null;
      setIsLoading(false);
      setIsValidating(false);
    }
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    let timer = null;
    fetchOnce();
    timer = setInterval(fetchOnce, 8000);
    return () => {
      aliveRef.current = false;
      if (timer) clearInterval(timer);
    };
  }, [fetchOnce]);

  const mutate = useCallback(() => fetchOnce(), [fetchOnce]);

  return {
    data,
    error,
    isLoading,
    isValidating,
    isError: Boolean(error),
    mutate,
  };
}

export default useDataFeed;
