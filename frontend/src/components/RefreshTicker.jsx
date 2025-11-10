import React, { useEffect, useState } from "react";

export default function RefreshTicker({ seconds = 30, onRefresh }) {
  const [left, setLeft] = useState(seconds);

  useEffect(() => {
    const t = setInterval(() => {
      setLeft((prev) => {
        if (prev <= 1) {
          onRefresh && onRefresh();
          return seconds;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [seconds, onRefresh]);

  return <div className="refresh-ticker">Auto refresh in {left}s</div>;
}
