#!/usr/bin/env python3
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

OPEN_APP = Path("/usr/local/libexec/audacity-studio-open-app")


def open_app(name: str) -> bool:
    result = subprocess.run(
        [str(OPEN_APP), name],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip() == "started"


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self.send_json(200, {"ok": True})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        app = {"/helio": "helio", "/downloader": "downloader"}.get(path)
        if app is None:
            self.send_json(404, {"error": "not found"})
            return
        try:
            self.send_json(200, {"started": open_app(app)})
        except (OSError, subprocess.SubprocessError) as error:
            self.send_json(503, {"error": str(error)})

    def log_message(self, format: str, *args) -> None:
        print(f"studio-apps: {format % args}", flush=True)


ThreadingHTTPServer(("127.0.0.1", 14503), Handler).serve_forever()
