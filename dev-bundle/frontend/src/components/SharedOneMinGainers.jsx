import React from "react";

const Pill = ({ symbol, price }) => {
  return (
    <div className="flex-shrink-0 mx-8 group">
      <div className="flex items-center gap-4 banner-pill px-4 py-2 rounded-full transition-all duration-300 group-hover:text-purple group-hover:text-shadow-purple">
        <span>{symbol}</span>
        <span className="font-mono text-base font-bold px-2 py-1 rounded text-teal">{price}</span>
      </div>
    </div>
  );
};

export default Pill;

<style>{`
  @keyframes banner-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
  /* Subtle, table-matching hover for banner pills */
  .banner-pill { background: transparent; }
  .banner-pill:hover {
    background: color-mix(in oklab, var(--panel, #0b0b0f) 85%, white 15%);
  }
`}</style>
