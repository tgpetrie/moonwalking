import React, { useEffect, useState } from "react";

export default function RefreshTicker({ seconds = 30, onRefresh }) {
  const [left, setLeft] = useState(seconds);

  useEffect(() => {
    const id = setInterval(() => {
      setLeft((prev) => {
        const next = prev - 1;
        if (next <= 0) {
          // reset visible counter
          // call onRefresh asynchronously to avoid React 'update during render' warnings
          setTimeout(() => onRefresh && onRefresh(), 0);
          return seconds;
        }
        return next;
      });
    }, 1000);

    return () => clearInterval(id);
  }, [seconds, onRefresh]);

  return <div className="refresh-ticker">Auto refresh in {left}s</div>;
}
