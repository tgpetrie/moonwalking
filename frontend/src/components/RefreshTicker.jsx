import React, { useEffect, useState } from "react";

export default function RefreshTicker({ seconds = 30, onRefresh }) {
  const [left, setLeft] = useState(seconds);

  useEffect(() => {
    const id = setInterval(() => {
      setLeft((prev) => {
        const next = prev - 1;
        if (next <= 0) {
          // reset visible counter
          // call onRefresh asynchronously and protect it with try/catch so failed fetches
          // don't surface as uncaught exceptions in the console
          setTimeout(async () => {
            try {
              await onRefresh?.();
            } catch (e) {
              // keep noise low but log for debugging
              // eslint-disable-next-line no-console
              console.warn("RefreshTicker: onRefresh failed", e);
            }
          }, 0);
          return seconds;
        }
        return next;
      });
    }, 1000);

    return () => clearInterval(id);
  }, [seconds, onRefresh]);

  return <div className="refresh-ticker">Auto refresh in {left}s</div>;
}
