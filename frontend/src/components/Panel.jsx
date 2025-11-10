// frontend/src/components/Panel.jsx
import React from "react";

export default function Panel({ title, children, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-header">
        <div className="panel-title">{title}</div>
        <div className="panel-line" />
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

