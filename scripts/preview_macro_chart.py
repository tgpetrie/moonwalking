"""Create an ignored, local Vite preview from an explicitly selected history export.

Reads an immutable JSON export, never an application database. The output embeds
the selected public-price snapshot for browser QA; it is not a production feed.
Run the frontend Vite server and open the printed relative URL.
"""

import argparse
import hashlib
import html
import json
from pathlib import Path


def build_preview(input_path: Path) -> Path:
    source = input_path.resolve(strict=True)
    if source.suffix.lower() != ".json":
        raise ValueError("Select a JSON history export, not a runtime store")
    payload = source.read_bytes()
    if len(payload) > 10 * 1024 * 1024:
        raise ValueError("History exports must be smaller than 10 MB")
    data = json.loads(payload)
    if data.get("contract") != "moonwalking.market-history/v1" and data.get(
        "schema_version"
    ) != "bhabit.chart-history.v1":
        raise ValueError("Unsupported history contract")
    digest = hashlib.sha256(payload).hexdigest()
    if source.read_bytes() != payload:
        raise RuntimeError("The source export changed during capture; retry when complete")
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    output_dir = frontend / ".runtime"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / f"macro-preview-v2-{digest[:12]}.html"
    symbol = data.get("instrument", {}).get("symbol") or data.get("asset", {}).get("symbol") or "Historical"
    title = html.escape(str(symbol), quote=True)
    # The JSON is data, not executable JS. Escape HTML delimiters so strings in
    # source metadata cannot close the inert script element.
    encoded = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c").replace(
        ">", "\\u003e"
    ).replace("&", "\\u0026")
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="history-sha256" content="{digest}">
<title>{title} chart map · local research preview</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>body{{margin:0;background:#050308}}</style>
</head><body><div id="root"></div>
<script id="history" type="application/json">{encoded}</script>
<script type="module">
import React from 'react';
import {{ createRoot }} from 'react-dom/client';
import MacroChartPage from '/src/mvp/MacroChartPage.jsx';
import {{ parseHistory }} from '/src/utils/macroChart.js';
import '/src/styles/design-tokens.css';
import '/src/styles/ui-system.css';
try {{
  const history = parseHistory(JSON.parse(document.getElementById('history').textContent));
  createRoot(document.getElementById('root')).render(React.createElement(MacroChartPage, {{initialHistory:history}}));
}} catch (error) {{
  document.getElementById('root').textContent = 'History unavailable: ' + error.message;
}}
</script></body></html>
"""
    if output.exists():
        if output.read_text(encoding="utf-8") != document:
            raise FileExistsError("Existing preview differs; preserve it and choose another snapshot")
    else:
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(document)
    print(json.dumps({"preview": str(output), "url_path": f"/.runtime/{output.name}", "source_sha256": digest}))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    build_preview(parser.parse_args().input)
