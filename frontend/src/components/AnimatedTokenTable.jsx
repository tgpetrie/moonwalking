// frontend/src/components/AnimatedTokenTable.jsx
import { LayoutGroup, motion, AnimatePresence } from "framer-motion";
import { useMemo } from "react";

const rowVariants = {
  initial: (rank) => ({
    opacity: 0,
    y: 12,
  }),
  animate: (rank) => ({
    opacity: 1,
    y: 0,
    transition: {
      y: { type: "spring", stiffness: 420, damping: 32 },
      opacity: { duration: 0.15 },
      delay: rank * 0.015, // stagger by rank
    },
  }),
  exit: (rank) => ({
    opacity: 0,
    y: -12,
    transition: { duration: 0.12 },
  }),
};

export function AnimatedTokenTable({ tokens, thead, renderRow, onRowClick, onRowHover }) {
  const rankMap = useMemo(() => {
    const map = {};
    tokens.forEach((t, i) => {
      map[t.symbol] = i; // 0-based index = rank
    });
    return map;
  }, [tokens]);

  const handleRowEnter = (index) => {
    if (!onRowHover) return;
    const total = tokens.length;
    const ratio = total > 1 ? index / (total - 1) : 0.5;
    const percent = 15 + ratio * 70; // avoid extreme edges
    onRowHover(percent, true);
  };

  const handleRowLeave = () => {
    if (!onRowHover) return;
    onRowHover(50, false); // Return to center/off
  };

  return (
    <LayoutGroup>
      <table className="bh-table token-table">
        {thead}
        <tbody>
          <AnimatePresence initial={false}>
            {tokens.map((token, index) => {
              const rank = rankMap[token.symbol] ?? index;
              return (
                <motion.tr
                  key={token.symbol}
                  layout
                  layoutId={token.symbol}
                  variants={rowVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                  custom={rank}
                  className="token-row"
                  onClick={() => onRowClick?.(token)}
                  onMouseEnter={() => handleRowEnter(index)}
                  onMouseLeave={handleRowLeave}
                >
                  {renderRow(token, index)}
                </motion.tr>
              );
            })}
          </AnimatePresence>
        </tbody>
      </table>
    </LayoutGroup>
  );
}

export default AnimatedTokenTable;
