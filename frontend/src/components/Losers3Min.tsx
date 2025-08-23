/* --- subtle breathing animation for panels --- */
.app-panel.breathe {
  animation: breathe 7s ease-in-out infinite;
  will-change: transform;
}
@keyframes breathe {
  0%, 100% { transform: translateZ(0) scale(1); }
  50%      { transform: translateZ(0) scale(1.012); }
}

/* --- enforce consistent table layout & alignment across all market tables --- */
.app-table {
  table-layout: fixed;
  width: 100%;
  border-collapse: collapse;
}
.app-table th,
.app-table td {
  padding: 8px 12px;
  vertical-align: middle;
}

/* Column widths: [rank] [symbol] [price] [pct] */
.app-table th:nth-child(1),
.app-table td:nth-child(1) { width: 3.25rem; text-align: left; }
.app-table th:nth-child(2),
.app-table td:nth-child(2) { width: auto; text-align: left; }
.app-table th:nth-child(3),
.app-table td:nth-child(3) { width: 7.5rem; text-align: right; }
.app-table th:nth-child(4),
.app-table td:nth-child(4) { width: 5.5rem; text-align: right; }

/* Numeric alignment for prices/percents */
.tabular-nums { font-variant-numeric: tabular-nums slashed-zero; }

/* Readability */
.app-table tbody tr:nth-child(odd) {
  background: color-mix(in oklab, var(--panel, #0b0b0f) 92%, white 8%);
}
.app-table tbody tr:hover {
  background: color-mix(in oklab, var(--panel, #0b0b0f) 85%, white 15%);
}
