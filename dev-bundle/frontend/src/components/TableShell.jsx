import React from 'react';

// TableShell: layout wrapper that enforces a consistent column structure.
// Props:
// - panelClass: optional class applied to the outer .app-panel (e.g. 'breathe')
// - colTemplate: optional grid-template-columns string (CSS) to override defaults
// - children, className: forwarded to the inner grid
export default function TableShell({ children, className = '', panelClass = '', colTemplate = '' }) {
  const defaultCols = 'minmax(0,1fr) 152px 108px 48px';
  const gridStyle = { gridTemplateColumns: colTemplate || defaultCols };

  return (
    <div className={`app-panel ${panelClass}`.trim()}>
      {/* inner grid keeps existing spacing & responsive behavior; use inline style for precise col widths */}
      <div
        className={`relative z-10 grid gap-x-3 items-start ${className}`}
        style={gridStyle}
      >
        {children}
      </div>
    </div>
  );
}
