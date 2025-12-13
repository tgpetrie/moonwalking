// frontend/src/components/tables/RankCell.jsx
import { motion } from "framer-motion";

export function RankCell({ rank }) {
  return (
    <td className="token-rank-cell cell-rank">
      <motion.span
        layout="position"
        className="token-rank-badge"
        initial={{ scale: 0.9, opacity: 0.7 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.14 }}
      >
        {rank}
      </motion.span>
    </td>
  );
}

export default RankCell;
