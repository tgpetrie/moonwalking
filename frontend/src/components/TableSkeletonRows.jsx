// frontend/src/components/TableSkeletonRows.jsx
export function TableSkeletonRows({ columns = 4, rows = 6, renderAs = "div" }) {
  const rowArr = Array.from({ length: rows });
  const colArr = Array.from({ length: columns });

  // Two rendering modes:
  // - renderAs === 'tr' -> output a sequence of <tr> elements (for use
  //   inside a table/tbody).
  // - renderAs === 'div' -> output div-based rows matching `TokenRowUnified`.
  if (renderAs === "tr") {
    return (
      <>
        {rowArr.map((_, rIndex) => (
          <tr key={rIndex} className="bh-row skeleton">
            {colArr.map((_, cIndex) => (
              <td key={cIndex} className="bh-cell">
                <span className="skel-cell" />
              </td>
            ))}
          </tr>
        ))}
      </>
    );
  }

  return (
    <>
      {rowArr.map((_, rIndex) => (
        <div key={rIndex} className="bh-row skeleton" aria-hidden="true">
          <div className="bh-row-hover-glow" />
          {colArr.map((_, cIndex) => (
            <div key={cIndex} className="bh-cell">
              <span className="skel-cell" />
            </div>
          ))}
        </div>
      ))}
    </>
  );
}
