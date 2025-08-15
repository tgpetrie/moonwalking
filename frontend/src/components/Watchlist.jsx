import React from 'react';
import GainersTable1Min from './GainersTable1Min.jsx';
import GainersTable from './GainersTable.jsx';
import LosersTable from './LosersTable.jsx';

function Watchlist() {
  return (
    <div>
      {/* 1-MIN row */}
      <div className="px-0">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-8">
          {/* left column aligns with 3-min Gainers */}
          <GainersTable1Min startRank={1} endRank={5} fixedRows={4} hideShowMore />
          {/* right column aligns with 3-min Losers */}
          <GainersTable1Min startRank={6} endRank={10} fixedRows={4} hideShowMore />
        </div>
      </div>

      {/* 3-MIN row */}
      <div className="px-0 mt-10">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-8">
          <GainersTable />
          <LosersTable />
        </div>
      </div>
    </div>
  );
}

export default Watchlist;