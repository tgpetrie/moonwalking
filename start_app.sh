import React from "react";
import { GainersTable } from "./GainersTable";
import { LosersTable } from "./LosersTable";

export function App() {
  return (
    <div>
      <h1>Market Overview</h1>
      <div className="tables-grid">
        <GainersTable someProp="value1" />
        <LosersTable someProp="value2" />
      </div>
    </div>
  );
}
