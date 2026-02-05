export default function SkeletonTable({ rows = 6 }) {
  return (
    <div className="skel-table">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skel-row">
          <div className="skel-cell skel-rank" />
          <div className="skel-cell skel-symbol" />
          <div className="skel-cell skel-price" />
          <div className="skel-cell skel-change" />
          <div className="skel-cell skel-mini" />
        </div>
      ))}
    </div>
  );
}
