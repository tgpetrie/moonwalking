import { motion } from "framer-motion";

export function ScrollingTicker({ items, renderItem, speedSeconds = 14 }) {
  const loopItems = [...(items || []), ...(items || [])];

  if (!loopItems.length) return null;

  return (
    <div className="ticker-viewport">
      <motion.div
        className="ticker-track"
        animate={{ x: ["0%", "-50%"] }}
        transition={{
          duration: speedSeconds,
          repeat: Infinity,
          ease: "linear",
        }}
      >
        {loopItems.map((item, index) => (
          <div key={`${item?.symbol || "item"}-${index}`} className="ticker-item">
            {renderItem(item)}
          </div>
        ))}
      </motion.div>
    </div>
  );
}

export default ScrollingTicker;
