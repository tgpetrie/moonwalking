import React from 'react';
import './skeleton.css';

export const SkeletonBlock = ({ w = '100%', h = 16, radius = 10, className = '', style = {} }) => (
  <div
    className={`bh-skel ${className}`}
    style={{ width: typeof w === 'number' ? `${w}px` : w, height: typeof h === 'number' ? `${h}px` : h, borderRadius: radius, ...style }}
  />
);

export const SkeletonText = ({ lines = 2, lineH = 12, gap = 8, heights = [], widths = [] }) => {
  const items = Array.from({ length: lines });
  return (
    <div className="skeleton-text">
      {items.map((_, index) => (
        <SkeletonBlock
          key={index}
          h={heights[index] || lineH}
          w={widths[index] || `${80 - index * 10}%`}
          radius={6}
          className="skeleton-line"
          style={{ marginBottom: index === lines - 1 ? 0 : gap }}
        />
      ))}
    </div>
  );
};

export const SkeletonRow = () => (
  <div className="skeleton-row">
    <SkeletonBlock w={36} h={36} radius={12} />
    <div className="skeleton-row-content">
      <SkeletonBlock w="140px" h={12} radius={6} style={{ marginBottom: 6 }} />
      <SkeletonBlock w="80px" h={10} radius={6} />
    </div>
    <SkeletonBlock w="60px" h={10} radius={6} />
  </div>
);

export const SkeletonCard = ({ children, className = '' }) => (
  <div className={`skeleton-card ${className}`}>
    {children}
  </div>
);
