// src/components/AnimatedTokenRow.jsx
import { motion } from "framer-motion";
import TokenRow from "./TokenRow";

// Use motion.create when available (newer framer-motion), otherwise fall back
// to the deprecated factory so this works across versions.
const motionFactory = typeof motion.create === "function" ? motion.create : motion;
export const AnimatedTokenRow = motionFactory(TokenRow);

export default AnimatedTokenRow;
