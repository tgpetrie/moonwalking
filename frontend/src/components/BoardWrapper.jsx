export function BoardWrapper({ children, highlightY = 50, highlightActive = false }) {
  const highlightClass = highlightActive ? "rabbit-highlight rabbit-highlight--active" : "rabbit-highlight";

  return (
    <div className="board-wrapper" style={{ "--rabbit-highlight-y": `${highlightY}%` }}>
      <div className="rabbit-layer">
        <div className="rabbit-base" />
        <div className={highlightClass} />
      </div>
      {children}
    </div>
  );
}

export default BoardWrapper;
