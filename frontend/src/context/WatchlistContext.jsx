import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { tickerFromSymbol } from "../utils/format";
import { getBackendCandidates, normalizeBase } from "../config/api.js";

const STORAGE_KEY = "bhabit_watchlist_v2";
const WatchlistContext = createContext(null);

const normalizeSymbol = (value) => {
  const ticker = tickerFromSymbol(value) || value;
  return String(ticker || "").trim().toUpperCase();
};

const toAddedPrice = (value) => {
  if (value == null || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
};

const buildGuestItem = ({ symbol, addedPrice, addedAt, id = null }) => ({
  id: id || `guest-${symbol}-${addedAt || Date.now()}`,
  symbol,
  addedPrice,
  addedAt: addedAt || Date.now(),
});

const dedupeItems = (items = []) => {
  const seen = new Set();
  const out = [];
  for (const entry of items) {
    const symbol = normalizeSymbol(entry?.symbol);
    if (!symbol || seen.has(symbol)) continue;
    seen.add(symbol);
    out.push(
      buildGuestItem({
        id: entry?.id || entry?.itemId || null,
        symbol,
        addedPrice: toAddedPrice(entry?.addedPrice),
        addedAt: entry?.addedAt || entry?.createdAt || Date.now(),
      })
    );
  }
  return out;
};

function readGuestItems() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? dedupeItems(parsed) : [];
  } catch {
    return [];
  }
}

function writeGuestItems(items = []) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(serializeGuestItems(items)));
  } catch {
    // Ignore localStorage write failures.
  }
}

function serializeGuestItems(items = []) {
  return items.map((entry) => ({
    id: entry.id || null,
    symbol: normalizeSymbol(entry.symbol),
    addedPrice: toAddedPrice(entry.addedPrice),
    addedAt: entry.addedAt || Date.now(),
  }));
}

function normalizeBackendItem(item = {}) {
  const symbol = normalizeSymbol(item.itemKey || item.symbol || item.title);
  if (!symbol) return null;
  return {
    id: item.id || null,
    symbol,
    addedPrice: toAddedPrice(item.addedPrice),
    addedAt: item.addedAt || item.createdAt || Date.now(),
  };
}

function pickPrimaryWatchlist(watchlists = [], preferredId = "") {
  if (!Array.isArray(watchlists) || watchlists.length === 0) return null;
  if (preferredId) {
    const exact = watchlists.find((watchlist) => watchlist?.id === preferredId);
    if (exact) return exact;
  }
  return watchlists[0] || null;
}

async function requestWatchlistApi(pathname, options = {}) {
  const candidates = getBackendCandidates();
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  const { method = "GET", body, allowUnauthorized = false } = options;
  let lastError = null;

  for (const base of candidates) {
    const normalizedBase = normalizeBase(base);
    const url = `${normalizedBase}${path}`;

    try {
      const response = await fetch(url, {
        method,
        credentials: "include",
        headers: {
          Accept: "application/json",
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });

      const contentType = response.headers.get("content-type") || "";
      const payload = contentType.includes("application/json")
        ? await response.json()
        : {};

      if (allowUnauthorized && response.status === 401) {
        return {
          ok: false,
          status: response.status,
          payload,
          base: normalizedBase,
        };
      }

      if (!response.ok) {
        lastError = new Error(
          payload?.error || payload?.message || `Request failed with status ${response.status}`
        );
        continue;
      }

      return {
        ok: true,
        status: response.status,
        payload,
        base: normalizedBase,
      };
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError || new Error(`Request failed for ${path}`);
}

export function WatchlistProvider({ children }) {
  const [items, setItems] = useState(() => readGuestItems());
  const [mode, setMode] = useState("guest");
  const [ready, setReady] = useState(false);
  const [syncError, setSyncError] = useState("");
  const [backendBase, setBackendBase] = useState("");
  const [activeWatchlistId, setActiveWatchlistId] = useState("");

  const applyBackendWatchlists = useCallback((watchlists = [], preferredId = "", base = "") => {
    const primary = pickPrimaryWatchlist(watchlists, preferredId);
    if (!primary) {
      setMode("authenticated");
      setItems([]);
      setActiveWatchlistId("");
      if (base) setBackendBase(base);
      return;
    }

    const nextItems = Array.isArray(primary.items)
      ? primary.items.map(normalizeBackendItem).filter(Boolean)
      : [];

    setMode("authenticated");
    setItems(dedupeItems(nextItems));
    setActiveWatchlistId(primary.id || "");
    if (base) setBackendBase(base);
  }, []);

  const fallBackToGuest = useCallback((message = "") => {
    setMode("guest");
    setActiveWatchlistId("");
    setBackendBase("");
    setSyncError(message);
    setItems(readGuestItems());
  }, []);

  const syncGuestItemsToBackend = useCallback(async (watchlists = [], base = "") => {
    const primary = pickPrimaryWatchlist(watchlists);
    const guestItems = readGuestItems();

    if (!primary || guestItems.length === 0) {
      return {
        watchlists,
        base,
        error: "",
      };
    }

    const existingSymbols = new Set(
      (primary.items || [])
        .map(normalizeBackendItem)
        .filter(Boolean)
        .map((entry) => entry.symbol)
    );

    const pending = guestItems.filter((entry) => {
      const symbol = normalizeSymbol(entry.symbol);
      const addedPrice = toAddedPrice(entry.addedPrice);
      return symbol && addedPrice !== null && !existingSymbols.has(symbol);
    });

    if (pending.length === 0) {
      writeGuestItems([]);
      return {
        watchlists,
        base,
        error: "",
      };
    }

    let nextPrimary = primary;
    let nextBase = base;
    const failed = [];

    for (const entry of pending) {
      const symbol = normalizeSymbol(entry.symbol);
      const addedPrice = toAddedPrice(entry.addedPrice);
      if (!symbol || addedPrice === null) {
        continue;
      }

      try {
        const result = await requestWatchlistApi(
          `/api/watchlists/${encodeURIComponent(primary.id)}/items`,
          {
            method: "POST",
            body: {
              itemKey: symbol,
              itemType: "Asset",
              title: symbol,
              notes: "",
              addedPrice,
            },
          }
        );

        if (result.payload?.watchlist) {
          nextPrimary = result.payload.watchlist;
        }
        if (result.base) {
          nextBase = result.base;
        }
      } catch {
        failed.push(entry);
      }
    }

    writeGuestItems(failed);

    return {
      watchlists: watchlists.map((watchlist) =>
        watchlist?.id === nextPrimary?.id ? nextPrimary : watchlist
      ),
      base: nextBase,
      error: failed.length
        ? `Could not sync ${failed.length} local watchlist item${failed.length === 1 ? "" : "s"}.`
        : "",
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const bootstrap = async () => {
      try {
        const result = await requestWatchlistApi("/api/auth/session", {
          allowUnauthorized: true,
        });

        if (cancelled) return;

        if (result.ok) {
          const synced = await syncGuestItemsToBackend(
            result.payload?.watchlists || [],
            result.base
          );

          if (cancelled) return;

          applyBackendWatchlists(
            synced.watchlists || result.payload?.watchlists || [],
            "",
            synced.base || result.base
          );
          setSyncError(synced.error || "");
        } else {
          fallBackToGuest("");
        }
      } catch {
        if (cancelled) return;
        fallBackToGuest("");
      } finally {
        if (!cancelled) setReady(true);
      }
    };

    bootstrap();

    return () => {
      cancelled = true;
    };
  }, [applyBackendWatchlists, fallBackToGuest]);

  useEffect(() => {
    if (mode !== "guest") return;
    writeGuestItems(items);
  }, [items, mode]);

  const has = useCallback(
    (symbol) => {
      const normalized = normalizeSymbol(symbol);
      return items.some((entry) => normalizeSymbol(entry.symbol) === normalized);
    },
    [items]
  );

  const addGuestItem = useCallback(({ symbol, price = null, baseline = null }) => {
    const normalized = normalizeSymbol(symbol);
    const addedPrice = toAddedPrice(baseline ?? price);
    if (!normalized || addedPrice === null) return;

    setItems((current) => {
      if (current.some((entry) => normalizeSymbol(entry.symbol) === normalized)) {
        return current;
      }
      return [
        ...current,
        buildGuestItem({
          symbol: normalized,
          addedPrice,
          addedAt: Date.now(),
        }),
      ];
    });
  }, []);

  const removeGuestItem = useCallback((symbol) => {
    const normalized = normalizeSymbol(symbol);
    setItems((current) =>
      current.filter((entry) => normalizeSymbol(entry.symbol) !== normalized)
    );
  }, []);

  const add = useCallback(
    async ({ symbol, baseline = null, price = null }) => {
      const normalized = normalizeSymbol(symbol);
      const addedPrice = toAddedPrice(baseline ?? price);
      if (!normalized) return;

      if (mode !== "authenticated" || !activeWatchlistId) {
        addGuestItem({ symbol: normalized, baseline, price });
        return;
      }

      if (addedPrice === null || has(normalized)) return;

      try {
        const result = await requestWatchlistApi(
          `/api/watchlists/${encodeURIComponent(activeWatchlistId)}/items`,
          {
            method: "POST",
            body: {
              itemKey: normalized,
              itemType: "Asset",
              title: normalized,
              notes: "",
              addedPrice,
            },
          }
        );

        applyBackendWatchlists(
          [{ ...(result.payload?.watchlist || {}), items: result.payload?.watchlist?.items || [] }],
          activeWatchlistId,
          result.base
        );
        setSyncError("");
      } catch (error) {
        setSyncError(error?.message || `Could not add ${normalized}.`);
      }
    },
    [activeWatchlistId, addGuestItem, applyBackendWatchlists, has, mode]
  );

  const remove = useCallback(
    async (symbol) => {
      const normalized = normalizeSymbol(symbol);
      if (!normalized) return;

      if (mode !== "authenticated" || !activeWatchlistId) {
        removeGuestItem(normalized);
        return;
      }

      const currentItem = items.find(
        (entry) => normalizeSymbol(entry.symbol) === normalized
      );
      if (!currentItem?.id) return;

      try {
        const result = await requestWatchlistApi(
          `/api/watchlists/${encodeURIComponent(activeWatchlistId)}/items/${encodeURIComponent(
            currentItem.id
          )}`,
          { method: "DELETE" }
        );

        applyBackendWatchlists(
          [{ ...(result.payload?.watchlist || {}), items: result.payload?.watchlist?.items || [] }],
          activeWatchlistId,
          result.base
        );
        setSyncError("");
      } catch (error) {
        setSyncError(error?.message || `Could not remove ${normalized}.`);
      }
    },
    [activeWatchlistId, applyBackendWatchlists, items, mode, removeGuestItem]
  );

  const toggle = useCallback(
    async ({ symbol, price = null, baseline = null }) => {
      const normalized = normalizeSymbol(symbol);
      if (!normalized) return;

      if (has(normalized)) {
        await remove(normalized);
        return;
      }

      await add({ symbol: normalized, price, baseline });
    },
    [add, has, remove]
  );

  const refreshFromData = useCallback(() => {
    // Legacy compatibility hook. The current board computes live price changes
    // from DataContext, so no watchlist-side refresh is required.
  }, []);

  const value = useMemo(
    () => ({
      items,
      has,
      add,
      remove,
      toggle,
      refreshFromData,
      mode,
      ready,
      isAuthenticated: mode === "authenticated",
      syncError,
      backendBase,
      activeWatchlistId,
    }),
    [
      items,
      has,
      add,
      remove,
      toggle,
      refreshFromData,
      mode,
      ready,
      syncError,
      backendBase,
      activeWatchlistId,
    ]
  );

  return (
    <WatchlistContext.Provider value={value}>
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const ctx = useContext(WatchlistContext);
  if (!ctx) throw new Error("useWatchlist must be used inside WatchlistProvider");
  return ctx;
}
