export default function PanelShell({
  title,
  timeframe,
  tone = "gain",
  align = "center",
  rightSlot,
  children,
  className = "",
}) {
  const toneClass = tone === "loss" ? "section-head-loss" : "section-head-gain";
  const lineClass =
    tone === "loss" ? "section-head-line-loss" : "section-head-line-gain";
  const alignClass = align === "left" ? "section-head--left" : "";
  const lineAlignClass = align === "left" ? "section-head-line--left" : "";
  const headAlignClass = align === "left" ? "panel-head--left" : "";

  return (
    <section className={`panel-shell ${className}`}>
      <div className={`panel-head ${headAlignClass}`}>
        <header className={`section-head ${toneClass} ${alignClass}`}>
          <span className="section-head-kicker">{title}</span>
          {timeframe ? <span className="section-head-timeframe">{timeframe}</span> : null}
          {rightSlot ? <span className="section-head-meta">{rightSlot}</span> : null}
        </header>
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}
