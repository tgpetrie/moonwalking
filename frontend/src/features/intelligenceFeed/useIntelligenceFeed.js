// Intelligence Feed — data hook (the integration point).
//
// This is the seam other surfaces mount against. It owns fetching, loading and
// error state, and the seen/dismissed transitions. It owns no rendering, so a
// Morning Feed UI can be built on top without touching this file.

import { useCallback, useEffect, useRef, useState } from "react";

import { buildFeedView } from "./intelligenceFeedAdapter.js";
import {
  fetchIntelligenceEvents,
  setIntelligenceEventStatus,
} from "./intelligenceFeedClient.js";

const EMPTY_FEED = { events: [], count: 0, isEmpty: true };

export function useIntelligenceFeed({
  limit = 20,
  enabled = true,
  // Injectable for tests and for a fixture-backed demo mode.
  fetcher = fetchIntelligenceEvents,
  statusSetter = setIntelligenceEventStatus,
} = {}) {
  const [feed, setFeed] = useState(EMPTY_FEED);
  const [status, setStatus] = useState(enabled ? "loading" : "idle");
  const [error, setError] = useState(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setStatus("loading");
    setError(null);
    try {
      const data = await fetcher({ limit });
      if (!mounted.current) return;
      setFeed(buildFeedView(data));
      setStatus("ready");
    } catch (err) {
      if (!mounted.current) return;
      // Not signed in is an expected state, not a failure to shout about.
      setError({ kind: err?.kind || "network_failure", message: err?.message || "" });
      setFeed(EMPTY_FEED);
      setStatus(err?.kind === "unauthorized" ? "unauthorized" : "error");
    }
  }, [enabled, fetcher, limit]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const markEvent = useCallback(
    async (eventId, nextStatus) => {
      try {
        await statusSetter(eventId, nextStatus);
      } catch {
        // A failed status write must never blank the feed the user is reading.
        return false;
      }
      if (!mounted.current) return true;
      setFeed((current) => {
        const events =
          nextStatus === "dismissed"
            ? current.events.filter((event) => event.id !== eventId)
            : current.events.map((event) =>
                event.id === eventId ? { ...event, status: nextStatus } : event
              );
        return { events, count: events.length, isEmpty: events.length === 0 };
      });
      return true;
    },
    [statusSetter]
  );

  return { feed, status, error, refresh, markEvent };
}

export default useIntelligenceFeed;
