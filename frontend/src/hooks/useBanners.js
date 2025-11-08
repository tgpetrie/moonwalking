import { useMemo } from "react";
import useUnifiedData from "./useUnifiedData";
import useDataFeed from "./useDataFeed";

export default function useBanners() {
  const { data } = useUnifiedData();
  const legacy = useDataFeed?.() || {};

  const banner1h = useMemo(() => {
    if (Array.isArray(data.banner_1h) && data.banner_1h.length > 0) return data.banner_1h;
    return legacy.banner1h || [];
  }, [data.banner_1h, legacy.banner1h]);

  const vol1h = useMemo(() => {
    if (Array.isArray(data.volume_1h) && data.volume_1h.length > 0) return data.volume_1h;
    return legacy.vol1h || [];
  }, [data.volume_1h, legacy.vol1h]);

  return { banner1h, vol1h };
}

