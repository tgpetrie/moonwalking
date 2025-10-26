import LemonPepperLayout from "../layouts/LemonPepperLayout";
import TopBannerScroll from "../components/TopBannerScroll.jsx";
import VolumeBannerScroll from "../components/BottomBannerScroll.jsx";
import GainersTable from "../components/tables/GainersTable";
import LosersTable from "../components/tables/LosersTable";
import GainersTable1mTwoCol from "../components/GainersTable1mTwoCol";

export default function LemonPepperHome() {
  const useTwoCol = (import.meta as any)?.env?.VITE_LPS_TWO_COL_1M === "1";
  return (
    <LemonPepperLayout>
      <section aria-label="One-hour price change" className="mb-6">
        <TopBannerScroll />
      </section>

      <section aria-label="Top gainers (1 minute)" className="mb-6">
        <div className="text-center">
          <h2 className="mb-3 font-prosto text-xl">Top Gainers · 1m</h2>
        </div>
        {useTwoCol ? (
          <GainersTable1mTwoCol />
        ) : (
          <GainersTable interval="1m" />
        )}
      </section>

      <section aria-label="Top movers (3 minutes)" className="mb-6">
        <div className="text-center">
          <h2 className="mb-3 font-prosto text-xl">Top Movers · 3m</h2>
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <h3 className="mb-3 font-prosto text-lg md:text-xl">Top Gainers</h3>
            <GainersTable interval="3m" />
          </div>
          <div>
            <h3 className="mb-3 font-prosto text-lg md:text-xl">Top Losers</h3>
            <LosersTable interval="3m" />
          </div>
        </div>
      </section>

      <section aria-label="One-hour volume change" className="mb-10">
        <VolumeBannerScroll />
      </section>
    </LemonPepperLayout>
  );
}
