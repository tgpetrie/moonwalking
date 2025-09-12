import React from "react";

export default function BannerScroll({ items = [], tone = "gainer" }) {
  const toneClass = tone === "loser" ? "text-purple-300" : "text-orange-300";
  // For seamless scrolling, we need to duplicate the content.
  // The animation moves the container by -50% of its width.
  const displayItems = items.length > 0 ? [...items, ...items] : [];

  return (
    <div className="relative overflow-hidden w-full rounded-xl bg-white/5">
      <div className="animate-[scrollLeft_30s_linear_infinite] whitespace-nowrap py-2 px-3">
        {displayItems.map((it, i) => (
          <span key={`${it.symbol}-${i}`} className={`mx-4 text-sm ${toneClass}`}>
            {it.text}
          </span>
        ))}
      </div>
      <style>{`
        @keyframes scrollLeft {
          0% { transform: translateX(0%); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}