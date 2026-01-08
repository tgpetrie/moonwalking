import { useEffect, useMemo, useRef, useState } from "react";

const defaultKeyForRow = (row, index) => {
  const base = row?.product_id ?? row?.symbol ?? row?.base ?? row?.ticker ?? null;
  return base ? String(base) : `row-${index}`;
};

const arraysEqual = (a, b) => {
  if (a === b) return true;
  if (!Array.isArray(a) || !Array.isArray(b)) return false;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false;
  }
  return true;
};

/**
 * Keeps value updates "live" but reorders the list on a cadence.
 *
 * - `rows` can update frequently.
 * - `sortFn` defines the *target* ordering.
 * - `ms` controls how often we allow the ordering to change.
 */
export function useReorderCadence(rows, sortFn, ms = 320) {
  const input = Array.isArray(rows) ? rows : [];

  const sorted = useMemo(() => {
    const copy = input.slice();
    if (typeof sortFn === "function") {
      copy.sort(sortFn);
    }
    return copy;
  }, [input, sortFn]);

  const sortedKeys = useMemo(() => sorted.map(defaultKeyForRow), [sorted]);

  const [order, setOrder] = useState(() => sortedKeys);
  const orderRef = useRef(order);
  useEffect(() => {
    orderRef.current = order;
  }, [order]);

  const byKey = useMemo(() => {
    const m = new Map();
    input.forEach((row, idx) => {
      m.set(defaultKeyForRow(row, idx), row);
    });
    return m;
  }, [input]);

  const displayRows = useMemo(() => {
    const used = new Set();
    const out = [];

    // Keep existing order, but refresh row objects (values).
    (order || []).forEach((key) => {
      const row = byKey.get(key);
      if (!row) return;
      used.add(key);
      out.push(row);
    });

    // Add any new rows not seen before, in target order.
    sorted.forEach((row, idx) => {
      const key = defaultKeyForRow(row, idx);
      if (used.has(key)) return;
      used.add(key);
      out.push(row);
    });

    return out;
  }, [byKey, sorted, order]);

  useEffect(() => {
    const nextOrder = sortedKeys;
    const prevOrder = orderRef.current || [];

    if (arraysEqual(prevOrder, nextOrder)) return;

    if (!ms || ms <= 0) {
      setOrder(nextOrder);
      return;
    }

    const timer = setTimeout(() => setOrder(nextOrder), ms);
    return () => clearTimeout(timer);
  }, [sortedKeys, ms]);

  return displayRows;
}
