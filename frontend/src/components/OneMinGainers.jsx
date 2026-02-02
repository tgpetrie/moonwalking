import React, { useMemo, useState } from "react";
import TokenRow from "./TokenRow.jsx";
import { baselineOrNull } from "../utils/num.js";

export default function OneMinGainers({ rows = [], loading = false, error = null, onInfo }) {
  const [expanded, setExpanded] = useState(false);

  // Visible rows: default 8, expand to 16 when user clicks "Show More".
  const visibleRows = useMemo(() => {
    const src = Array.isArray(rows) ? rows : [];
    const cap = expanded ? 16 : 8;
    return src.slice(0, cap);
  }, [rows, expanded]);

  const visibleCount = visibleRows.length;
  const hasData = visibleCount > 0;

  // Layout: single full-width column when 4 or fewer rows; otherwise two columns.
  const isSingleColumn = visibleCount <= 4;++++