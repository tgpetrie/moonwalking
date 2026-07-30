// Founder-funded beta allowance indicator. Honest and small: "2 of 3 beta
// analyses remaining", or the exhausted message. No subscription/BYOK promises.
import PropTypes from "prop-types";

export default function BetaAllowanceMeter({ used, remaining, limit, exhausted, label }) {
  const dots = Array.from({ length: limit }, (_, i) => i < remaining);
  return (
    <div className="abx-allowance" data-exhausted={exhausted ? "1" : "0"} role="status">
      {!exhausted ? (
        <span className="abx-allowance-dots" aria-hidden="true">
          {dots.map((filled, i) => (
            <span key={i} className="abx-dot" data-filled={filled ? "1" : "0"} />
          ))}
        </span>
      ) : null}
      <span>{label}</span>
      <span className="abx-source-meta" style={{ marginLeft: "auto" }}>
        {used}/{limit} used
      </span>
    </div>
  );
}

BetaAllowanceMeter.propTypes = {
  used: PropTypes.number.isRequired,
  remaining: PropTypes.number.isRequired,
  limit: PropTypes.number.isRequired,
  exhausted: PropTypes.bool.isRequired,
  label: PropTypes.string.isRequired,
};
