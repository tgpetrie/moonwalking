import React, { useEffect, useRef } from "react";

export default function Marquee({ children, speed = 45 }: { children: React.ReactNode; speed?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.style.setProperty("--marquee-speed", `${speed}s`);
  }, [speed]);
  return (
    <div className="overflow-visible">
      <div
        ref={ref}
        className="flex items-center animate-[marquee_var(--marquee-speed)_linear_infinite]"
        style={{ gap: "2rem", paddingBlock: "6px" }}
      >
        {children}
        {children}
      </div>
    </div>
  );
}
