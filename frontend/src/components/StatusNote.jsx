import React from 'react';
import PropTypes from 'prop-types';

// Minimal StatusNote used by table components to display loading/error/empty states.
export default function StatusNote({ state = 'loading', message = null }) {
  if (state === 'loading') {
    return (
      <div className="w-full py-8 text-center text-sm text-gray-300">Loading…</div>
    );
  }
  if (state === 'error') {
    return (
      <div className="w-full py-8 text-center text-sm text-red-400">{message || 'An error occurred'}</div>
    );
  }
  // empty or default
  return (
    <div className="w-full py-8 text-center text-sm text-gray-400">{message || 'No data available'}</div>
  );
}

StatusNote.propTypes = {
  state: PropTypes.oneOf(['loading', 'error', 'empty']),
  message: PropTypes.string,
};
