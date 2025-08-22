
import React, { useRef } from 'react';

// Outlined purple star with gold/orange fill option
export default function StarIcon({ filled, onClick, className = '' }) {
  const svgRef = useRef(null);
  // Animate scale on click
  const handleClick = (e) => {
    if (svgRef.current) {
      svgRef.current.animate([
        { transform: 'scale(1)' },
        { transform: 'scale(1.3)' },
        { transform: 'scale(1)' }
      ], {
        duration: 250,
        easing: 'cubic-bezier(.4,2,.6,1)'
      });
    }
    if (onClick) onClick(e);
  };
  return (
    <svg
      ref={svgRef}
      onClick={handleClick}
      className={`w-4 h-4 cursor-pointer transition-all duration-200 hover:scale-125 active:scale-90 ${filled ? 'drop-shadow-[0_0_6px_#FEA400]' : ''} ${className}`}
      fill={filled ? 'url(#gold-gradient)' : 'none'}
      stroke="#a259ff" // purple border
      strokeWidth="2"
      viewBox="0 0 24 24"
      style={{ filter: filled ? 'drop-shadow(0 0 4px #FEA400)' : undefined, transition: 'filter 0.2s' }}
    >
      <defs>
        <linearGradient id="gold-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FFE7A0" />
          <stop offset="100%" stopColor="#FEA400" />
        </linearGradient>
      </defs>
      <polygon
        points="12,2 15,9 22,9.5 17,14.5 18.5,22 12,18 5.5,22 7,14.5 2,9.5 9,9"
        strokeLinejoin="round"
      />
    </svg>
  );
}
