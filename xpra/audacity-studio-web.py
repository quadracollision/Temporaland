#!/usr/bin/env python3
import cgi
import base64
import hashlib
import hmac
import html
import http.cookies
import json
import mimetypes
import os
import queue
import secrets
import shutil
import struct
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

PASSWORD_FILE = Path("/etc/audacity-studio/password")
IMPORT_DIR = Path("/srv/audacity-studio/imports")
EXPORT_DIR = Path("/srv/audacity-studio/exports")
MAX_UPLOAD = 10 * 1024 * 1024
SESSION_TTL = 24 * 60 * 60
ALLOWED_SUFFIXES = {
    ".wav", ".wave", ".mp3", ".flac", ".ogg", ".opus",
    ".aif", ".aiff", ".m4a", ".mp4", ".caf", ".au",
}
SESSIONS: dict[str, float] = {}
AUDIO_CLIENTS: set[queue.Queue[bytes]] = set()
AUDIO_CLIENTS_LOCK = threading.Lock()


def authenticated(cookie_header: str | None) -> bool:
    if not cookie_header:
        return False
    cookies = http.cookies.SimpleCookie(cookie_header)
    morsel = cookies.get("temporaman_session")
    if not morsel:
        return False
    expires = SESSIONS.get(morsel.value, 0)
    if expires <= time.time():
        SESSIONS.pop(morsel.value, None)
        return False
    return True


def unique_target(filename: str) -> Path:
    safe_name = Path(filename).name.replace("\x00", "").strip()
    if not safe_name or Path(safe_name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("Unsupported audio file type")
    target = IMPORT_DIR / safe_name
    stem, suffix = target.stem, target.suffix
    counter = 2
    while target.exists():
        target = IMPORT_DIR / f"{stem}-{counter}{suffix}"
        counter += 1
    return target


def websocket_frame(payload: bytes) -> bytes:
    length = len(payload)
    if length < 126:
        return bytes((0x82, length)) + payload
    if length <= 65535:
        return b"\x82\x7e" + struct.pack("!H", length) + payload
    return b"\x82\x7f" + struct.pack("!Q", length) + payload


def capture_audio() -> None:
    command = [
        "/usr/bin/parec", "--device=studio.monitor", "--raw",
        "--format=s16le", "--rate=48000", "--channels=2",
        "--latency-msec=40",
    ]
    while True:
        try:
            with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
                while process.stdout:
                    chunk = process.stdout.read(3840)
                    if not chunk:
                        break
                    with AUDIO_CLIENTS_LOCK:
                        clients = list(AUDIO_CLIENTS)
                    for client in clients:
                        try:
                            client.put_nowait(chunk)
                        except queue.Full:
                            try:
                                client.get_nowait()
                                client.put_nowait(chunk)
                            except (queue.Empty, queue.Full):
                                pass
        except OSError as error:
            print(f"audio capture: {error}", flush=True)
        time.sleep(1)


class Handler(BaseHTTPRequestHandler):
    server_version = "TemporamanUpload/1.0"

    def send_text(self, status: int, body: str, content_type: str = "text/plain; charset=utf-8") -> None:
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def require_auth(self) -> bool:
        if authenticated(self.headers.get("Cookie")):
            return True
        self.send_text(401, "Authentication required")
        return False

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/auth":
            self.send_text(204 if authenticated(self.headers.get("Cookie")) else 401, "")
            return
        if path == "/audio":
            if not self.require_auth():
                return
            websocket_key = self.headers.get("Sec-WebSocket-Key")
            if self.headers.get("Upgrade", "").lower() != "websocket" or not websocket_key:
                self.send_text(426, "WebSocket upgrade required")
                return
            accept = base64.b64encode(
                hashlib.sha1((websocket_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
            ).decode()
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            client: queue.Queue[bytes] = queue.Queue(maxsize=25)
            with AUDIO_CLIENTS_LOCK:
                AUDIO_CLIENTS.add(client)
            try:
                while True:
                    self.connection.sendall(websocket_frame(client.get()))
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with AUDIO_CLIENTS_LOCK:
                    AUDIO_CLIENTS.discard(client)
            return
        if path == "/files":
            if not self.require_auth():
                return
            files = []
            for area, directory in (("imports", IMPORT_DIR), ("exports", EXPORT_DIR)):
                directory.mkdir(parents=True, exist_ok=True)
                for item in directory.iterdir():
                    if item.is_file() and not item.name.startswith("."):
                        stat = item.stat()
                        files.append({
                            "area": area, "name": item.name,
                            "size": stat.st_size, "modified": stat.st_mtime,
                        })
            files.sort(key=lambda item: item["modified"], reverse=True)
            self.send_text(200, json.dumps({"files": files[:250]}, separators=(",", ":")),
                           "application/json; charset=utf-8")
            return
        if path == "/download":
            if not self.require_auth():
                return
            query = parse_qs(parsed.query)
            area = query.get("area", [""])[0]
            name = query.get("name", [""])[0]
            directory = {"imports": IMPORT_DIR, "exports": EXPORT_DIR}.get(area)
            if directory is None or not name or Path(name).name != name:
                self.send_text(400, "Invalid file")
                return
            target = directory / name
            try:
                if target.resolve().parent != directory.resolve() or not target.is_file():
                    raise FileNotFoundError
                size = target.stat().st_size
                content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(size))
                self.send_header("Content-Disposition",
                                 f"attachment; filename*=UTF-8''{quote(target.name)}")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                with target.open("rb") as source:
                    shutil.copyfileobj(source, self.wfile, length=1024 * 1024)
            except FileNotFoundError:
                self.send_text(404, "File not found")
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if path == "/upload":
            if not self.require_auth():
                return
            files = sorted(IMPORT_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)
            rows = "".join(
                f"<li>{html.escape(item.name)} <small>{item.stat().st_size / 1048576:.1f} MB</small></li>"
                for item in files if item.is_file()
            ) or "<li>No samples uploaded yet.</li>"
            page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Upload samples · Temporaman Shrine</title><style>
body{{margin:0;background:#11131a;color:#f4f5f7;font:16px system-ui,sans-serif}}main{{max-width:680px;margin:48px auto;padding:28px}}
.card{{background:#1b1f2a;border:1px solid #343b4d;border-radius:16px;padding:24px}}h1{{margin-top:0}}p,small{{color:#b8c0d4}}
input[type=file]{{display:block;width:100%;box-sizing:border-box;padding:20px;margin:18px 0;border:1px dashed #66708a;border-radius:12px;background:#141721;color:#fff}}
button,a.button{{display:inline-block;border:0;border-radius:10px;padding:12px 18px;background:#7c5cff;color:#fff;font-weight:700;text-decoration:none;cursor:pointer}}
a.secondary{{background:#303647;margin-left:8px}}li{{padding:7px 0}}code{{color:#d9d2ff}}
</style></head><body><main><div class="card"><h1>Upload samples</h1>
<p>Select audio files, then import them in Audacity from <code>/srv/audacity-studio/imports</code>.</p>
<form method="post" enctype="multipart/form-data"><input type="file" name="sample" accept="audio/*,.wav,.flac,.mp3,.ogg,.opus,.aif,.aiff,.m4a,.caf" multiple required>
<button type="submit">Upload to Audacity</button><a class="button secondary" href="/temporaman/shrine.html">Back to shrine</a></form>
<h2>Available samples</h2><ul>{rows}</ul></div></main></body></html>"""
            self.send_text(200, page, "text/html; charset=utf-8")
            return
        self.send_text(404, "Not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/login":
            length = min(int(self.headers.get("Content-Length", "0")), 4096)
            password = parse_qs(self.rfile.read(length).decode(errors="replace")).get("password", [""])[0]
            expected = PASSWORD_FILE.read_text().strip()
            if not hmac.compare_digest(password, expected):
                self.send_text(401, "Incorrect password")
                return
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = time.time() + SESSION_TTL
            self.send_response(204)
            self.send_header("Set-Cookie", f"temporaman_session={token}; Path=/temporaman; Max-Age={SESSION_TTL}; HttpOnly; Secure; SameSite=Strict")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/upload":
            if not self.require_auth():
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_UPLOAD:
                self.send_text(413, "Upload is empty or too large")
                return
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", ""), "CONTENT_LENGTH": str(length)},
            )
            fields = form["sample"] if "sample" in form else []
            if not isinstance(fields, list):
                fields = [fields]
            saved = []
            IMPORT_DIR.mkdir(parents=True, exist_ok=True)
            try:
                for field in fields:
                    if not getattr(field, "filename", None):
                        continue
                    target = unique_target(field.filename)
                    temporary = target.with_name(f".{target.name}.{secrets.token_hex(6)}.upload")
                    with temporary.open("wb") as output:
                        shutil.copyfileobj(field.file, output, length=1024 * 1024)
                    os.replace(temporary, target)
                    saved.append(target.name)
            except ValueError as error:
                self.send_text(400, str(error))
                return
            if not saved:
                self.send_text(400, "No audio files were selected")
                return
            self.send_response(303)
            self.send_header("Location", "/temporaman/upload")
            self.end_headers()
            return
        self.send_text(404, "Not found")

    def log_message(self, format: str, *args) -> None:
        print(f"upload-web: {format % args}", flush=True)


if __name__ == "__main__":
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=capture_audio, daemon=True, name="audio-capture").start()
    ThreadingHTTPServer(("127.0.0.1", 14501), Handler).serve_forever()
