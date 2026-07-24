// First-value screen: never an empty chat box. Two sample positions demonstrate
// the well-supported (SOL) and sparse-data (SHDW) cases up front.
import PropTypes from "prop-types";
import { SAMPLE_POSITIONS } from "../fixtures/samplePositions.js";
import { fmtPrice } from "../askBhabitAdapter.js";
import { toneClass } from "./toneClass.js";

const COVERAGE_TONE = { rich: "positive", sparse: "warning" };
const COVERAGE_LABEL = { rich: "Well supported", sparse: "Sparse data" };

export default function SamplePositions({ selectedId, onSelect }) {
  return (
    <div className="abx-section">
      <p className="abx-eyebrow">Start with a sample</p>
      <div className="abx-samples">
        {SAMPLE_POSITIONS.map((p) => (
          <button
            key={p.id}
            type="button"
            className="abx-sample"
            data-selected={selectedId === p.id ? "1" : "0"}
            aria-pressed={selectedId === p.id}
            onClick={() => onSelect(p)}
          >
            <div className="abx-sample-asset">{p.asset}</div>
            <div className="abx-sample-name">{p.name}</div>
            <span className={`abx-sample-coverage ${toneClass(COVERAGE_TONE[p.coverage])}`}>
              {COVERAGE_LABEL[p.coverage]}
            </span>
            <div className="abx-sample-meta">
              {p.quantity} {p.asset} · entry {fmtPrice(p.entryPrice)}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

SamplePositions.propTypes = {
  selectedId: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
};
