import React from "react";
import OneMinGainersColumns from "./OneMinGainersColumns.jsx";

type Handlers = {
  onSelectCoin?: (symbol: string) => void;
  onOpenSymbol?: (symbol: string, opts?: Record<string, unknown>) => void;
};

export default function GainersTable1mTwoCol({ onSelectCoin, onOpenSymbol }: Handlers = {}) {
  return (
    <div className="w-full flex justify-center">
      <div className="w-full max-w-3xl grid grid-cols-1 sm:grid-cols-2 gap-4">
        {React.createElement(OneMinGainersColumns as any, { side: "left", compact: true, onSelectCoin, onOpenSymbol })}
        {React.createElement(OneMinGainersColumns as any, { side: "right", compact: true, onSelectCoin, onOpenSymbol })}
      </div>
    </div>
  );
}
