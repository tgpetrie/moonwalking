/* eslint-disable react/prop-types */
import React from 'react';
import GainersTable from './GainersTable';

// Thin wrapper to render the main 3-minute gainers view.
// Uses the same component but with different defaults for row counts.
export default function GainersTable3Min(props) {
  return <GainersTable {...props} initialRows={10} maxRows={20} />;
}
