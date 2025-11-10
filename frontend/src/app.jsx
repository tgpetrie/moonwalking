import React, { useState } from "react";
import useUnifiedData from "./hooks/useUnifiedData.js";
import Gainers1m from "./components/Gainers1m.jsx";
import Gainers3m from "./components/Gainers3m.jsx";
import Losers3m from "./components/Losers3m.jsx";
import ThreeMinSection from "./components/ThreeMinSection.jsx";

export default function App() {
  const { data, loading, errs } = useUnifiedData();
  const [infoSymbol, setInfoSymbol] = useState(null);

  return (
    <main className="min-h-screen bg-black text-white relative overflow-x-hidden">
      {/* background bunny */}
      <img
        src="/purple-rabbit-bg.png"
        alt=""
        className="pointer-events-none select-none opacity-[0.025] absolute inset-0 mx-auto max-w-6xl w-full h-full object-contain"
      />

      <div className="relative z-10 max-w-6xl mx-auto px-4 py-10 flex flex-col gap-14">
        <Gainers1m
          rows={data.gainers_1m || []}
          loading={loading}
          error={errs.gainers_1m}
          onInfo={setInfoSymbol}
        />

        <ThreeMinSection
          gainers={data.gainers_3m || []}
          losers={data.losers_3m || []}
          loadingGainers={loading}
          loadingLosers={loading}
          onInfo={setInfoSymbol}
          onShowMore={() => console.log("Show more clicked")}
        />
      </div>
    </main>
  );
}
