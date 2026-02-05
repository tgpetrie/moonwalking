import { useEffect, useRef } from "react";

export function BoardWrapper({ children }) {
  const wrapRef = useRef(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;

    const root = document.documentElement;

    let lastRow = null;
    let hoverOn = false;

    const setBand = (top, height, on) => {
      const isOn = Boolean(on);
      const safeTop = isOn ? Math.max(0, Number(top) || 0) : -9999;
      const safeHeight = isOn ? Math.max(0, Number(height) || 0) : 0;

      root.style.setProperty("--bh-hover-top", `${safeTop}px`);
      root.style.setProperty("--bh-hover-h", `${Math.max(0, Number(height) || 0)}px`);
      root.style.setProperty("--bh-hover-h", `${safeHeight}px`);
      root.style.setProperty("--bh-hover-on", isOn ? "1" : "0");
      hoverOn = isOn;
    };

    const updateFromLastRow = () => {
      if (!hoverOn || !lastRow) return;
      const r = lastRow.getBoundingClientRect();
      setBand(r.top, r.height, true);
    };

    const onMove = (e) => {
      const row = e?.target?.closest?.(".bh-row");
      if (!row) {
        lastRow = null;
        return setBand(-9999, 0, false);
      }
      lastRow = row;
      const r = row.getBoundingClientRect();
      setBand(r.top, r.height, true);
    };

    const onLeave = () => {
      lastRow = null;
      setBand(-9999, 0, false);
    };

    el.addEventListener("mousemove", onMove, { passive: true });
    el.addEventListener("mouseleave", onLeave, { passive: true });
    window.addEventListener("scroll", updateFromLastRow, { passive: true });
    window.addEventListener("resize", updateFromLastRow, { passive: true });

    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
      window.removeEventListener("scroll", updateFromLastRow);
      window.removeEventListener("resize", updateFromLastRow);
    };
  }, []);

  return (
    <div ref={wrapRef} className="board-wrapper">
      {children}
    </div>
  );
}

export default BoardWrapper;
