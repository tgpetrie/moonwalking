import React from 'react';

// Shared control placeholder; wire to parent state to truly expand both columns together.
export default function SharedOneMinGainers({ children }) {
  return (
    <div className="w-full flex justify-center">
      {children ?? (
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-black/40 text-xs text-gray-300 border border-gray-700">
          <span>Top 10 shown • 2 columns</span>
        </div>
      )}
    </div>
  );
}
