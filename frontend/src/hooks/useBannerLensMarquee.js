import { useEffect, useRef } from "react";

/**
 * Autoplays a banner track and applies a soft lens that magnifies items
 * near the center of the viewport. Assumes the track contains a doubled
 * list of items so it can loop seamlessly.
 */
export function useBannerLensMarquee(speedPxPerSec = 40, deps = []) {
  const wrapRef = useRef(null);
  const trackRef = useRef(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    const track = trackRef.current;
    if (!wrap || !track) return undefined;

    let rafId;
    let lastTs = 0;
    let offset = 0;
    let halfWidth = 0;

    const measure = () => {
      // Track is looped (items duplicated), so half the width is one cycle.
      halfWidth = (track.scrollWidth || 0) / 2;
    };

    const applyLens = () => {
      const wrapRect = wrap.getBoundingClientRect();
      const centerX = wrapRect.left + wrapRect.width / 2;
      // Radius adapts to viewport but stays within sane limits.
      const lensRadius = Math.min(420, Math.max(180, wrapRect.width * 0.26));

      for (const child of track.children) {
        const rect = child.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const dist = Math.abs(cx - centerX);
        const t = Math.min(1, dist / lensRadius);
        const scale = 1 + (1 - t) * 0.30; // up to +30% at center
        const glow = (1 - t); // 0..1

        child.style.setProperty("--banner-scale", scale.toFixed(3));
        child.style.setProperty("--banner-lens-alpha", glow.toFixed(3));
      }
    };

    const tick = (ts) => {
      if (!lastTs) lastTs = ts;
      const dt = (ts - lastTs) / 1000;
      lastTs = ts;

      if (halfWidth <= 0 && track.scrollWidth) {
        halfWidth = track.scrollWidth / 2;
      }

      if (halfWidth > 0) {
        offset += speedPxPerSec * dt;
        if (offset >= halfWidth) offset -= halfWidth;
      }

      if (track.children.length) {
        track.style.transform = `translate3d(${-offset}px, 0, 0)`;
        applyLens();
      }
      rafId = requestAnimationFrame(tick);
    };

    measure();
    applyLens();
    rafId = requestAnimationFrame(tick);

    const ro = new ResizeObserver(() => {
      measure();
      applyLens();
    });
    ro.observe(wrap);
    ro.observe(track);

    return () => {
      cancelAnimationFrame(rafId);
      ro.disconnect();
      track.style.transform = "";
    };
  }, [speedPxPerSec, ...deps]);

  return { wrapRef, trackRef };
}

export default useBannerLensMarquee;
