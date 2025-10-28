import { useEffect, useRef, useState } from "react";
import { fetchJson } from "../lib/api";
import {
  ensureSubscribed,
  getSocket,
  isSocketConnected,
  on,
} from "../lib/socket";

/**
 * Socket-first data hook with REST polling fallback.
 * - Listens to a Socket.IO event when connected.
 * - Polls a REST endpoint when socket is unavailable.
 * - Automatically switches back to socket when it reconnects.
 */
function useHybridLive({
  endpoint,
  eventName,
  pollMs = 6000,
  initial = [],
}) {
  const [data, setData] = useState(initial);
  const [source, setSource] = useState("init");
  const pollId = useRef(null);
  const socketUnsub = useRef(null);
  const cleanupFns = useRef([]);

  useEffect(() => {
    let active = true;

    const stopPolling = () => {
      if (pollId.current) {
        clearInterval(pollId.current);
        pollId.current = null;
      }
    };

    const stopSocket = () => {
      if (socketUnsub.current) {
        socketUnsub.current();
        socketUnsub.current = null;
      }
    };

    const startPolling = async () => {
      stopSocket();
      if (pollId.current) return;
      setSource("poll");

      const run = async () => {
        try {
          const next = await fetchJson(endpoint);
          if (active) setData(Array.isArray(next) ? next : []);
        } catch (err) {
          if (active) {
            console.warn("[poll] request failed", endpoint, err?.message || err);
          }
        }
      };

      await run();
      pollId.current = setInterval(run, pollMs);
    };

    const startSocket = () => {
      stopPolling();
      if (socketUnsub.current) {
        socketUnsub.current();
        socketUnsub.current = null;
      }
      const socket = getSocket();
      ensureSubscribed(eventName);
      socketUnsub.current = on(eventName, (payload) => {
        if (active) setData(Array.isArray(payload) ? payload : []);
      });
      setSource("socket");
    };

    // Always warm up the socket instance so connect events fire.
    getSocket();

    if (isSocketConnected()) {
      startSocket();
    } else {
      startPolling();
    }

    cleanupFns.current.push(on("connect", () => active && startSocket()));
    cleanupFns.current.push(on("disconnect", () => active && startPolling()));
    cleanupFns.current.push(
      on("connect_error", () => active && startPolling()),
    );

    return () => {
      active = false;
      stopPolling();
      if (socketUnsub.current) {
        socketUnsub.current();
        socketUnsub.current = null;
      }
      cleanupFns.current.forEach((fn) => {
        try {
          fn?.();
        } catch {
          // ignore
        }
      });
      cleanupFns.current = [];
    };
  }, [endpoint, eventName, pollMs]);

  return { data, source };
}

export default useHybridLive;
export { useHybridLive };
