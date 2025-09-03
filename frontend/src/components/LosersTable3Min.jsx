/* eslint-disable react/prop-types */
import React from 'react';
import LosersTable from './LosersTable';

// Thin wrapper to render the main 3-minute losers view with adjusted defaults
export default function LosersTable3Min(props) {
  return <LosersTable {...props} initialRows={10} maxRows={20} />;
}
