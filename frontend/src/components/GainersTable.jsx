import React from 'react';
import PropTypes from 'prop-types';
import ErrorBanner from './ErrorBanner.jsx';

export default function GainersTable({ rows = [], loading = false, error = null }) {
	if (error || !rows?.length) return <ErrorBanner label="Failed to load (3-min)" />;

	return (
		<div className="w-full">
			{/* Render rows if present; simplified view for dev */}
			{rows.map((r, i) => (
				<div key={r.symbol || i} className="py-2 border-b border-white/6">
					<div className="flex justify-between">
						<div className="font-medium">{r.symbol}</div>
						<div className="font-mono tabular-nums">{r.price ?? '—'}</div>
					</div>
				</div>
			))}
		</div>
	);
}

GainersTable.propTypes = {
	rows: PropTypes.arrayOf(PropTypes.object),
	loading: PropTypes.bool,
	error: PropTypes.any,
};

