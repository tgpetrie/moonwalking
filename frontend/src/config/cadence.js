const readMs = (value, fallback, { allowZero = false } = {}) => {
  if (value == null || value === "") return fallback;

  const num = Number(value);
  if (!Number.isFinite(num)) return fallback;
  if (allowZero && num === 0) return 0;
  if (num <= 0) return fallback;
  return Math.round(num);
};

export function deriveDashboardCadence(env = {}) {
  const FAST_1M_MS = readMs(env.VITE_FAST_1M_MS, 3800);
  const BACKOFF_1M_MS = Math.max(readMs(env.VITE_BACKOFF_1M_MS, 9000), FAST_1M_MS);
  const POLL_JITTER_MS = readMs(env.VITE_POLL_JITTER_MS, 320, { allowZero: true });
  const PUBLISH_UI_MS = readMs(env.VITE_PUBLISH_UI_MS, 4000, { allowZero: true });

  // Preserve the logical hierarchy from MW_SPEC:
  // 1m updates fastest, 3m publishes slower, banners publish slowest.
  const publish3mRaw = readMs(env.VITE_PUBLISH_3M_MS, 12000);
  const PUBLISH_3M_MS = Math.max(publish3mRaw, FAST_1M_MS + 1000);

  const publishBannerRaw = readMs(env.VITE_PUBLISH_BANNER_MS, 30000);
  const PUBLISH_BANNER_MS = Math.max(publishBannerRaw, PUBLISH_3M_MS + FAST_1M_MS);

  return {
    FAST_1M_MS,
    BACKOFF_1M_MS,
    POLL_JITTER_MS,
    PUBLISH_UI_MS,
    PUBLISH_3M_MS,
    PUBLISH_BANNER_MS,
  };
}

export default deriveDashboardCadence;
