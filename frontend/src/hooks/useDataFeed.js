import { useMemo } from "react";
import { useData } from "../context/DataContext";

// Compatibility wrapper: legacy consumers expect useDataFeed to provide
// { data, error, isLoading, isValidating, mutate }.
// We now source everything from DataContext so all consumers share the same
// resilience (base auto-detect, last-good cache, stale freeze).
export function useDataFeed() {
  const ctx = useData();

  const value = useMemo(() => {
    if (!ctx) {
      return {
        data: null,
        error: null,
        isLoading: true,
        isValidating: false,
        isError: false,
        mutate: null,
        status: "DOWN",
      };
    }
    const { data, error, loading, refetch, connectionStatus, lastGoodLatestBySymbol, alerts, getActiveAlert } = ctx;
    return {
      data,
      error,
      isLoading: loading,
      isValidating: connectionStatus === "LIVE" ? false : Boolean(loading),
      isError: Boolean(error),
      mutate: refetch,
      status: connectionStatus,
      backendBase: ctx.backendBase,
      lastGoodLatestBySymbol,
      alerts: alerts || [],
      getActiveAlert: getActiveAlert || (() => null),
    };
  }, [ctx]);

  return value;
}

export default useDataFeed;
