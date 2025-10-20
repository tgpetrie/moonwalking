import PropTypes from "prop-types";

export default function ErrorBanner({ label = "Failed to load" }) {
  return (
    <div
      className="w-full flex items-center justify-center py-6"
      role="status"
      aria-live="polite"
    >
      <span
        className="text-sm md:text-base leading-tight tracking-wide"
        style={{ color: "rgba(255,180,170,.85)" }}
      >
        {label}
      </span>
    </div>
  );
}

ErrorBanner.propTypes = {
  label: PropTypes.string,
};
