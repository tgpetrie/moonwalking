#!/usr/bin/env python3
"""Local browser interface for the Moonwalking AI helper."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

import local_ai


ROOT = Path(__file__).resolve().parents[1]
UI_FILE = ROOT / "tools" / "local_ai_gui" / "index.html"
MAX_REQUEST_BYTES = 100_000


def ollama_status() -> dict[str, object]:
    tags_url = local_ai.DEFAULT_OLLAMA_URL.replace("/api/chat", "/api/tags")
    try:
        with urlopen(tags_url, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError):
        return {
            "online": False,
            "model": local_ai.DEFAULT_MODEL,
            "modelInstalled": False,
        }
    names = {item.get("name") for item in payload.get("models", [])}
    return {
        "online": True,
        "model": local_ai.DEFAULT_MODEL,
        "modelInstalled": local_ai.DEFAULT_MODEL in names,
    }


class LocalAIHandler(BaseHTTPRequestHandler):
    server_version = "MoonwalkingLocalAI/1.0"

    def _json(self, payload: dict[str, object], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _allowed_host(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0].lower()
        return host in {"127.0.0.1", "localhost"}

    def do_GET(self) -> None:  # noqa: N802
        if not self._allowed_host():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if self.path == "/":
            try:
                body = UI_FILE.read_bytes()
            except OSError:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "UI file is missing")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/status":
            self._json(ollama_status())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if not self._allowed_host():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if self.path != "/api/chat":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json({"error": "Invalid request length"}, HTTPStatus.BAD_REQUEST)
            return
        if size <= 0 or size > MAX_REQUEST_BYTES:
            self._json({"error": "Request is empty or too large"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            data = json.loads(self.rfile.read(size).decode("utf-8"))
            mode = str(data.get("mode", "ask"))
            if mode == "ask":
                question = str(data.get("question", "")).strip()
                if not question:
                    raise ValueError("Enter a project question")
                raw_files = data.get("files", [])
                if not isinstance(raw_files, list) or len(raw_files) > 8:
                    raise ValueError("Supply no more than eight project files")
                files = [str(item).strip() for item in raw_files if str(item).strip()]
                prompt = local_ai.build_ask_prompt(question, files)
            elif mode == "review":
                prompt = local_ai.build_diff_prompt()
            elif mode == "triage":
                log_text = str(data.get("log", "")).strip()
                if not log_text:
                    raise ValueError("Paste a log or error message to analyze")
                prompt = local_ai.build_triage_prompt(log_text, "GUI input")
            else:
                raise ValueError("Unknown assistant mode")

            answer = local_ai.ask_ollama(
                prompt,
                model=local_ai.DEFAULT_MODEL,
                url=local_ai.DEFAULT_OLLAMA_URL,
                context_tokens=8192,
                max_output_tokens=900,
            )
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._json({"answer": answer, "mode": mode, "model": local_ai.DEFAULT_MODEL})

    def log_message(self, format: str, *args: object) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Moonwalking Local AI web interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    url = f"http://{args.host}:{args.port}/"
    try:
        server = ThreadingHTTPServer((args.host, args.port), LocalAIHandler)
    except OSError:
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
