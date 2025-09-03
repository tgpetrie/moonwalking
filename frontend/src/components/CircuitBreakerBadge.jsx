import React from 'react';
import { motion } from 'framer-motion';

const stateConfig = {
  open: {
    color: 'text-red-400',
    bg: 'bg-red-900/40',
    border: 'border-red-600',
    icon: '⚡',
    label: 'Circuit Open',
    description: 'Service degraded - using fallbacks'
  },
  'half-open': {
    color: 'text-amber-400', 
    bg: 'bg-amber-900/40',
    border: 'border-amber-600',
    icon: '⚠️',
    label: 'Testing Recovery',
    description: 'Attempting to restore service'
  },
  closed: {
    color: 'text-green-400',
    bg: 'bg-green-900/40', 
    border: 'border-green-600',
    icon: '✓',
    label: 'Healthy',
    description: 'All systems operational'
  }
};

export default function CircuitBreakerBadge({ state = 'closed', failures = 0, lastFailure, className = '' }) {
  const config = stateConfig[state] || stateConfig.closed;
  const isUnhealthy = state !== 'closed';

  return (
    <motion.div
      className={`inline-flex items-center gap-2 px-2 py-1 rounded-full border text-xs font-mono ${config.bg} ${config.border} ${config.color} ${className}`}
      animate={isUnhealthy ? { scale: [1, 1.02, 1] } : {}}
      transition={{ duration: 2, repeat: isUnhealthy ? Infinity : 0, ease: 'easeInOut' }}
      title={`${config.description}${failures > 0 ? ` (${failures} recent failures)` : ''}`}
    >
      <span className="text-[10px]" role="img" aria-label={config.label}>
        {config.icon}
      </span>
      <span className="font-semibold tracking-wide">
        {config.label}
      </span>
      {failures > 0 && (
        <span className="px-1 py-0.5 rounded bg-red-600/60 text-white text-[9px] leading-none">
          {failures}
        </span>
      )}
    </motion.div>
  );
}