import { useData } from "./useData";

/**
 * Temporary compatibility wrapper.
 *
 * Older components import `useHybridLive` from "../hooks/useHybridLive"
 * to get a data object with { gainers_3m, losers_3m, gainers_1m, banners, meta, ... }.
 *
 * For now, we simply delegate to `useData()`, which already returns the unified
 * payload from `/api/data`. If later you want true "hybrid live" behavior
 * (e.g. mixing snapshots with websocket ticks), you can evolve this hook
 * without touching all the table components again.
 */
export function useHybridLive() {
  return useData();
}

export default useHybridLive;
