// Shared framer-motion variants for list and row animations
export const rowVariants = {
  hidden: { opacity: 0, y: 6 },
  visible: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
};

export const listVariants = {
  visible: {
    transition: {
      staggerChildren: 0.05,
    },
  },
};
