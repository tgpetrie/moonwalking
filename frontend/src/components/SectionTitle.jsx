import React from "react";

export default function SectionTitle({ text, tone = "gold", center = false }) {
  const color = tone === "purple" ? "text-bh.purple" : "text-bh.gold";
  const border = tone === "purple" ? "border-bh.purple/60 shadow-glowPurple" : "border-bh.gold/60 shadow-glowGold";

  return (
    <div className={center ? "text-center" : ""}>
      <div className={"font-mono text-[13px] tracking-wide font-semibold " + color}>{text}</div>
      <div
        className={
          "mt-1 h-px w-full max-w-[180px] " + (center ? "mx-auto " : "") + "border-b " + border
        }
      />
    </div>
  );
}
