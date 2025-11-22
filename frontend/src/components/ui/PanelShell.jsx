export default function PanelShell({
  title,
  subtitle,
  rightSlot,
  children,
  className = "",
}) {
  return (
    <section className={`panel-shell ${className}`}>
      <header className="panel-head">
        <div className="panel-title">
          <h2>{title}</h2>
          {subtitle && <span className="panel-sub">{subtitle}</span>}
        </div>
        {rightSlot && <div className="panel-right">{rightSlot}</div>}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}
