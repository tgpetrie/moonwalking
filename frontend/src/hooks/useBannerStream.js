import { useState, useEffect } from "react";
import { ensureSubscribed, getSocketInstance, on } from "../lib/socket";

function normalizeBannerPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.data)) return payload.data;
  return [];
}

export function useBannerStream() {
  const [priceBanner, setPriceBanner] = useState([]); // from 'banner1h'
  const [volBanner, setVolBanner] = useState([]); // from 'vol1h'
  const [ts, setTs] = useState(null);

  useEffect(() => {
  const socket = getSocketInstance();
  if (!socket) return undefined;

  ensureSubscribed("banner1h");
  ensureSubscribed("vol1h");

    const handlePrice = (payload) => {
      const rows = normalizeBannerPayload(payload);
      setPriceBanner(rows);
      setTs(Date.now());
    };

    const handleVol = (payload) => {
      const rows = normalizeBannerPayload(payload);
      setVolBanner(rows);
      setTs(Date.now());
    };

    const unsubscribePrice = on("banner1h", handlePrice);
    const unsubscribeVol = on("vol1h", handleVol);

    return () => {
      if (typeof unsubscribePrice === "function") unsubscribePrice();
      if (typeof unsubscribeVol === "function") unsubscribeVol();
    };
  }, []);

  return { priceBanner, volBanner, ts };
}
