import PropTypes from 'prop-types';
import React from 'react';

export default function InfoIcon({ onClick, title = 'Info' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      className="ml-2 inline-flex items-center justify-center rounded-md text-xs px-1.5 py-1 border border-transparent hover:border-gray-700/60 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-purple-500/70"
    >
      <span className="font-mono text-gray-300">i</span>
    </button>
  );
}

InfoIcon.propTypes = {
  onClick: PropTypes.func,
  title: PropTypes.string,
};
