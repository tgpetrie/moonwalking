"""Offline safety checks for local preview generation."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from preview_macro_chart import build_preview


class PreviewTests(unittest.TestCase):
    def test_uses_the_loaded_symbol_and_preserves_inert_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "frontend").mkdir()
            source = root / "fixture.json"
            # Synthetic metadata only; not historical market observations.
            data = {"schema_version": "bhabit.chart-history.v1", "instrument": {"symbol": "FET"},
                    "source": {"note": "</script><script>alert(1)</script>"}}
            source.write_text(json.dumps(data), encoding="utf-8")
            with patch("preview_macro_chart.__file__", str(root / "scripts" / "preview.py")), contextlib.redirect_stdout(io.StringIO()):
                result = build_preview(source)
            content = result.read_text(encoding="utf-8")
            self.assertIn("<title>FET chart map", content)
            self.assertNotIn("</script><script>alert", content)
            self.assertIn("\\u003c/script\\u003e", content)

    def test_escapes_title_and_never_overwrites_an_existing_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "frontend").mkdir()
            source = root / "fixture.json"
            source.write_text(json.dumps({"schema_version": "bhabit.chart-history.v1", "instrument": {"symbol": "<unsafe>"}}), encoding="utf-8")
            with patch("preview_macro_chart.__file__", str(root / "scripts" / "preview.py")), contextlib.redirect_stdout(io.StringIO()):
                result = build_preview(source)
                self.assertIn("&lt;unsafe&gt; chart map", result.read_text(encoding="utf-8"))
                result.write_text("preserved test artifact", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    build_preview(source)
                self.assertEqual(result.read_text(encoding="utf-8"), "preserved test artifact")


if __name__ == "__main__":
    unittest.main()
