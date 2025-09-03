import React from 'react';
import { motion } from 'framer-motion';

const shimmer = {
  initial: { backgroundPosition: '-200px 0' },
  animate: { backgroundPosition: '200px 0' },
  transition: {
    duration: 1.5,
    repeat: Infinity,
    ease: 'linear'
  }
};

function SkeletonRow({ delay = 0 }) {
  return (
    <motion.div 
      className="px-0 py-1 mb-1"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
    >
      <div className="rounded-xl p-4 h-[96px] bg-gray-900/40 border border-gray-800">
  {/* Mobile Layout Skeleton */}
  <div className="mw-mobile-only">
          <div className="flex items-center justify-between py-3 px-2">
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-full bg-purple-900/40 animate-pulse" />
              <div>
                <div className="h-5 bg-gray-700 rounded mb-2 w-16 animate-pulse" />
                <div className="h-4 bg-gray-700 rounded w-20 animate-pulse" />
              </div>
            </div>
            <div className="h-6 bg-gray-700 rounded w-16 animate-pulse" />
          </div>
        </div>

  {/* Desktop Grid Layout Skeleton */}
  <div className="mw-desktop-grid grid-cols-[minmax(0,1fr)_152px_108px_28px] gap-x-4 items-start h-full">
          <div className="flex items-center gap-4 min-w-0">
            <div className="w-8 h-8 rounded-full bg-purple-900/40 animate-pulse shrink-0" />
            <div className="flex items-center gap-3 min-w-0">
              <motion.div 
                className="h-4 bg-gray-700 rounded w-16"
                style={{
                  background: 'linear-gradient(90deg, #374151 0%, #4b5563 50%, #374151 100%)',
                  backgroundSize: '200px 100%',
                }}
                {...shimmer}
              />
              <div className="flex gap-1">
                {[1, 2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full bg-purple-900/40 animate-pulse" />
                ))}
              </div>
            </div>
          </div>
          
          <div className="w-[152px] pr-6 text-right space-y-1">
            <div className="h-5 bg-gray-700 rounded w-full animate-pulse" />
            <div className="h-3 bg-gray-700 rounded w-3/4 animate-pulse ml-auto" />
          </div>
          
          <div className="w-[108px] pr-1.5 text-right space-y-1">
            <div className="h-5 bg-gray-700 rounded w-full animate-pulse" />
            <div className="h-3 bg-gray-700 rounded w-1/2 animate-pulse ml-auto" />
          </div>
          
          <div className="w-[28px] text-right">
            <div className="w-4 h-4 rounded bg-gray-700 animate-pulse ml-auto" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default function TableSkeleton({ rows = 5, title }) {
  return (
    <div className="w-full">
      {title && (
        <div className="mb-6">
          <div className="h-6 bg-gray-700 rounded w-48 animate-pulse mb-4" />
          <div className="w-48 h-2 bg-gray-700 rounded animate-pulse" />
        </div>
      )}
      
      <div className="space-y-1" role="status" aria-label="Loading table data">
        {Array.from({ length: rows }, (_, i) => (
          <SkeletonRow key={i} delay={i * 0.1} />
        ))}
      </div>
      
      <div className="sr-only">Loading cryptocurrency data...</div>
    </div>
  );
}