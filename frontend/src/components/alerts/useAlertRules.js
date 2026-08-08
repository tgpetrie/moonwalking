import { useCallback, useRef, useState } from "react";
import * as api from "./alertRulesApi.js";

/**
 * State for the Alerts Center.
 *
 * Each slice (rules / recommendations / history) loads lazily on first tab
 * activation, so opening the Market Feed costs no requests at all.
 *
 * `authRequired` is tracked separately from `error`: being signed out is a
 * normal state that deserves a calm prompt, not a failure message.
 *
 * Optimistic updates are used only where rollback is trivial — dismiss,
 * pause/resume, delete. Create and accept are not optimistic because the
 * server assigns the id and owns validation.
 *
 * Optimistic state is mirrored into a ref and always written through
 * `applyRules`/`applyRecs`. Capturing a rollback snapshot inside a setState
 * updater would be a race: the updater has not necessarily run by the time a
 * request rejects, so the "snapshot" could still be the initial empty array
 * and the rollback would wipe the list instead of restoring it.
 */
export default function useAlertRules() {
  const [rules, setRules] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [events, setEvents] = useState([]);

  const rulesRef = useRef([]);
  const recsRef = useRef([]);

  const applyRules = useCallback((next) => {
    const value = typeof next === "function" ? next(rulesRef.current) : next;
    rulesRef.current = value;
    setRules(value);
  }, []);

  const applyRecs = useCallback((next) => {
    const value = typeof next === "function" ? next(recsRef.current) : next;
    recsRef.current = value;
    setRecommendations(value);
  }, []);

  const [loading, setLoading] = useState({ rules: false, recs: false, events: false });
  const [errors, setErrors] = useState({ rules: null, recs: null, events: null });
  const [authRequired, setAuthRequired] = useState(false);

  // Tracks which slices have been fetched so tabs load once, not on every view.
  const loaded = useRef({ rules: false, recs: false, events: false });

  const setSlice = (setter, key, value) =>
    setter((prev) => ({ ...prev, [key]: value }));

  const handleError = useCallback((key, err) => {
    if (err?.isAuthRequired) {
      setAuthRequired(true);
      setSlice(setErrors, key, null);
      return;
    }
    setSlice(setErrors, key, err?.message || "Something went wrong.");
  }, []);

  const load = useCallback(
    async (key, fn, setData, { force = false } = {}) => {
      if (loaded.current[key] && !force) return;
      setSlice(setLoading, key, true);
      setSlice(setErrors, key, null);
      try {
        const data = await fn();
        setData(data);
        setAuthRequired(false);
        loaded.current[key] = true;
      } catch (err) {
        handleError(key, err);
      } finally {
        setSlice(setLoading, key, false);
      }
    },
    [handleError]
  );

  const loadRules = useCallback(
    (opts) => load("rules", api.listRules, applyRules, opts),
    [load, applyRules]
  );

  const loadRecommendations = useCallback(
    (opts) =>
      load("recs", () => api.listRecommendations({ refresh: true }), applyRecs, opts),
    [load, applyRecs]
  );

  const loadHistory = useCallback(
    (opts) => load("events", () => api.listHistory({ limit: 50 }), setEvents, opts),
    [load]
  );

  // ── mutations ──────────────────────────────────────────────────────────────

  const createRule = useCallback(
    async (payload) => {
      // Not optimistic: the server assigns the id and owns validation, and its
      // error message is the one worth showing.
      const rule = await api.createRule(payload);
      if (rule) applyRules((prev) => [rule, ...prev]);
      return rule;
    },
    [applyRules]
  );

  const acceptRecommendation = useCallback(
    async (recId) => {
      const rule = await api.acceptRecommendation(recId);
      applyRecs((prev) => prev.filter((r) => r.id !== recId));
      if (rule) {
        applyRules((prev) => [rule, ...prev]);
        loaded.current.rules = true;
      }
      return rule;
    },
    [applyRules, applyRecs]
  );

  const dismissRecommendation = useCallback(
    async (recId) => {
      const snapshot = recsRef.current;
      applyRecs((prev) => prev.filter((r) => r.id !== recId));
      try {
        await api.dismissRecommendation(recId);
        return true;
      } catch (err) {
        applyRecs(snapshot); // rollback
        throw err;
      }
    },
    [applyRecs]
  );

  const setRuleStatus = useCallback(
    async (ruleId, nextStatus) => {
      const snapshot = rulesRef.current;
      applyRules((prev) =>
        prev.map((r) => (r.id === ruleId ? { ...r, status: nextStatus } : r))
      );
      try {
        const fn = nextStatus === "paused" ? api.pauseRule : api.resumeRule;
        const updated = await fn(ruleId);
        if (updated) {
          applyRules((prev) => prev.map((r) => (r.id === ruleId ? updated : r)));
        }
        return true;
      } catch (err) {
        applyRules(snapshot); // rollback
        throw err;
      }
    },
    [applyRules]
  );

  const removeRule = useCallback(
    async (ruleId) => {
      const snapshot = rulesRef.current;
      applyRules((prev) => prev.filter((r) => r.id !== ruleId));
      try {
        await api.deleteRule(ruleId);
        return true;
      } catch (err) {
        applyRules(snapshot); // rollback
        throw err;
      }
    },
    [applyRules]
  );

  return {
    rules,
    recommendations,
    events,
    loading,
    errors,
    authRequired,
    loadRules,
    loadRecommendations,
    loadHistory,
    createRule,
    acceptRecommendation,
    dismissRecommendation,
    setRuleStatus,
    removeRule,
  };
}
