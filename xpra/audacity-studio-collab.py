#!/usr/bin/env python3
import base64
import hashlib
import json
import mimetypes
import queue
import re
import secrets
import shutil
import socket
import sqlite3
import struct
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

DATABASE = Path("/srv/audacity-studio/collab.sqlite3")
IMPORT_DIR = Path("/srv/audacity-studio/imports")
EXPORT_DIR = Path("/srv/audacity-studio/exports")
CLIENTS: dict[str, "Client"] = {}
STATE_LOCK = threading.RLock()
CONTROLLER_ID: str | None = None
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass
class Client:
    client_id: str
    connection: object
    nickname: str = "Guest"
    color: str = "#7c5cff"
    joined: bool = False
    outgoing: queue.Queue[bytes] = field(
        default_factory=lambda: queue.Queue(maxsize=256))


def initialize_database() -> None:
    with sqlite3.connect(DATABASE) as database:
        database.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL NOT NULL, "
            "nickname TEXT NOT NULL, color TEXT NOT NULL, body TEXT NOT NULL)"
        )


def frame(payload: bytes, opcode: int = 1) -> bytes:
    length = len(payload)
    header = bytes((0x80 | opcode,))
    if length < 126:
        return header + bytes((length,)) + payload
    if length <= 65535:
        return header + b"\x7e" + struct.pack("!H", length) + payload
    return header + b"\x7f" + struct.pack("!Q", length) + payload


def read_exact(connection, length: int) -> bytes:
    data = b""
    while len(data) < length:
        chunk = connection.recv(length - len(data))
        if not chunk:
            raise ConnectionError("connection closed")
        data += chunk
    return data


def read_frame(connection) -> tuple[int, bytes]:
    first, second = read_exact(connection, 2)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", read_exact(connection, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", read_exact(connection, 8))[0]
    if length > 65536:
        raise ValueError("frame too large")
    mask = read_exact(connection, 4) if masked else b""
    payload = read_exact(connection, length)
    if masked:
        payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
    return opcode, payload


def disconnect(client: Client) -> None:
    try:
        client.connection.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        client.connection.close()
    except OSError:
        pass


def queue_frame(client: Client, encoded_frame: bytes) -> bool:
    try:
        client.outgoing.put_nowait(encoded_frame)
        return True
    except queue.Full:
        # A browser that cannot consume a few seconds of updates must not
        # block presence/chat delivery for every other visitor.
        disconnect(client)
        return False


def send(client: Client, message: dict) -> bool:
    encoded = json.dumps(message, separators=(",", ":")).encode()
    return queue_frame(client, frame(encoded))


def write_frames(client: Client) -> None:
    try:
        while True:
            client.connection.sendall(client.outgoing.get())
    except (BrokenPipeError, ConnectionError, OSError):
        disconnect(client)


def broadcast(message: dict, exclude: str | None = None) -> None:
    with STATE_LOCK:
        clients = list(CLIENTS.values())
    for client in clients:
        if client.client_id != exclude and client.joined:
            send(client, message)


def presence() -> None:
    with STATE_LOCK:
        users = [
            {"id": item.client_id, "nickname": item.nickname, "color": item.color}
            for item in CLIENTS.values() if item.joined
        ]
        controller = CONTROLLER_ID
    broadcast({"type": "presence", "users": users, "controller": controller})


def history() -> list[dict]:
    with sqlite3.connect(DATABASE) as database:
        rows = database.execute(
            "SELECT created, nickname, color, body FROM messages ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return [
        {"type": "chat", "time": created, "nickname": nickname, "color": color, "text": body}
        for created, nickname, color, body in reversed(rows)
    ]


def save_message(client: Client, text: str) -> dict:
    created = time.time()
    with sqlite3.connect(DATABASE) as database:
        database.execute(
            "INSERT INTO messages(created, nickname, color, body) VALUES (?, ?, ?, ?)",
            (created, client.nickname, client.color, text),
        )
    return {"type": "chat", "time": created, "nickname": client.nickname, "color": client.color, "text": text}


def clean_nickname(value) -> str:
    nickname = " ".join(str(value or "").strip().split())[:24]
    return nickname or "Guest"


def clean_color(value) -> str:
    color = str(value or "")
    return color.lower() if COLOR_PATTERN.fullmatch(color) else "#7c5cff"


def remove_client(client: Client) -> None:
    global CONTROLLER_ID
    with STATE_LOCK:
        CLIENTS.pop(client.client_id, None)
        if CONTROLLER_ID == client.client_id:
            CONTROLLER_ID = None
    presence()


def handle_message(client: Client, message: dict) -> None:
    global CONTROLLER_ID
    message_type = message.get("type")
    if message_type == "join":
        client.nickname = clean_nickname(message.get("nickname"))
        client.color = clean_color(message.get("color"))
        client.joined = True
        send(client, {"type": "welcome", "id": client.client_id, "history": history()})
        presence()
        return
    if not client.joined:
        return
    if message_type == "profile":
        client.nickname = clean_nickname(message.get("nickname"))
        client.color = clean_color(message.get("color"))
        presence()
    elif message_type == "chat":
        text = str(message.get("text") or "").strip()[:500]
        if text:
            broadcast(save_message(client, text))
    elif message_type == "cursor":
        try:
            x = max(0.0, min(1.0, float(message.get("x", 0))))
            y = max(0.0, min(1.0, float(message.get("y", 0))))
        except (TypeError, ValueError):
            return
        broadcast({
            "type": "cursor", "id": client.client_id, "nickname": client.nickname,
            "color": client.color, "x": x, "y": y, "visible": bool(message.get("visible", True)),
        }, exclude=client.client_id)
    elif message_type == "control":
        action = message.get("action")
        response = None
        with STATE_LOCK:
            if action == "take" and CONTROLLER_ID is None:
                CONTROLLER_ID = client.client_id
            elif action == "release" and CONTROLLER_ID == client.client_id:
                CONTROLLER_ID = None
            elif action == "request":
                if CONTROLLER_ID is None:
                    CONTROLLER_ID = client.client_id
                elif CONTROLLER_ID != client.client_id:
                    controller = CLIENTS.get(CONTROLLER_ID)
                    if controller and controller.joined:
                        response = (controller, {
                            "type": "control_request",
                            "requester": {
                                "id": client.client_id,
                                "nickname": client.nickname,
                                "color": client.color,
                            },
                        })
            elif action in ("grant", "deny") and CONTROLLER_ID == client.client_id:
                target_id = str(message.get("target") or "")
                target = CLIENTS.get(target_id)
                if target and target.joined and target_id != client.client_id:
                    if action == "grant":
                        CONTROLLER_ID = target_id
                    response = (target, {
                        "type": "control_response",
                        "accepted": action == "grant",
                        "nickname": client.nickname,
                    })
        if response:
            send(*response)
        presence()


class Handler(BaseHTTPRequestHandler):
    server_version = "TemporamanCollab/1.0"

    def send_text(self, status: int, body: str,
                  content_type: str = "text/plain; charset=utf-8") -> None:
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/files":
            files = []
            for area, directory in (("imports", IMPORT_DIR), ("exports", EXPORT_DIR)):
                directory.mkdir(parents=True, exist_ok=True)
                for item in directory.iterdir():
                    if item.is_file() and not item.name.startswith("."):
                        stat = item.stat()
                        files.append({"area": area, "name": item.name,
                                      "size": stat.st_size, "modified": stat.st_mtime})
            files.sort(key=lambda item: item["modified"], reverse=True)
            self.send_text(200, json.dumps({"files": files[:250]}, separators=(",", ":")),
                           "application/json; charset=utf-8")
            return
        if parsed.path == "/download":
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
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(target.name)[0]
                                 or "application/octet-stream")
                self.send_header("Content-Length", str(target.stat().st_size))
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
        if parsed.path != "/collab":
            self.send_error(404)
            return
        key = self.headers.get("Sec-WebSocket-Key")
        if self.headers.get("Upgrade", "").lower() != "websocket" or not key:
            self.send_error(426)
            return
        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

        client = Client(secrets.token_urlsafe(9), self.connection)
        with STATE_LOCK:
            CLIENTS[client.client_id] = client
        threading.Thread(target=write_frames, args=(client,), daemon=True).start()
        try:
            while True:
                opcode, payload = read_frame(self.connection)
                if opcode == 8:
                    break
                if opcode == 9:
                    queue_frame(client, frame(payload, 10))
                    continue
                if opcode != 1:
                    continue
                try:
                    message = json.loads(payload.decode())
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(message, dict):
                    handle_message(client, message)
        except (ConnectionError, OSError, ValueError):
            pass
        finally:
            remove_client(client)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path not in ("/request-upload", "/request-download"):
            self.send_error(404)
            return
        with STATE_LOCK:
            controller = CLIENTS.get(CONTROLLER_ID) if CONTROLLER_ID else None
            clients = [client for client in CLIENTS.values() if client.joined]
        message_type = "upload_request" if path == "/request-upload" else "download_request"
        if controller is not None and controller.joined:
            delivered = send(controller, {"type": message_type})
        else:
            # In open-control mode there is no way for the desktop-side curl
            # request to identify which browser clicked. Offer the chooser to
            # each connected visitor; only the person who wants it uses it.
            delivered = any([send(client, {"type": message_type}) for client in clients])
        if not delivered:
            self.send_response(409)
        else:
            self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        print(f"collab: {format % args}", flush=True)


if __name__ == "__main__":
    initialize_database()
    ThreadingHTTPServer(("127.0.0.1", 14502), Handler).serve_forever()
