export default function SkeletonBlock({ lines = 3, className = "" }) {
  return (
    <div className={`skel-wrap ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skel-line" />
      ))}
    </div>
  );
}
