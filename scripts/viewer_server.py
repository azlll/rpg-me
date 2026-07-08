#!/usr/bin/env python3
"""Start, reuse, inspect, and stop the local rpg-me history viewer."""

import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "output"
DEFAULT_HISTORY_ROOT = DEFAULT_OUTPUT_ROOT / "history"
STATE_FILENAME = ".rpg-me-viewer.json"


def read_json(path, default):
    path = Path(path)
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remove_file(path):
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass


def state_path(output_root):
    return Path(output_root) / STATE_FILENAME


def normalize_roots(output_root, history_root):
    output = Path(output_root).resolve()
    history = Path(history_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    history.mkdir(parents=True, exist_ok=True)
    try:
        history.relative_to(output)
    except ValueError as exc:
        raise SystemExit(f"ERROR: history root must be inside output root: {history}") from exc
    return output, history


def request_json(url, timeout=1.0, method="GET", body=None, headers=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def health_url(port):
    return f"http://127.0.0.1:{port}/api/health"


def shutdown_url(port):
    return f"http://127.0.0.1:{port}/api/shutdown"


def probe_state(state, output_root, history_root):
    port = int(state.get("port") or 0)
    token = state.get("token", "")
    if not port or not token:
        return None
    try:
        health = request_json(health_url(port), timeout=0.7)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    if health.get("status") != "ok":
        return None
    if Path(health.get("outputRoot", "")).resolve() != Path(output_root).resolve():
        return None
    if Path(health.get("historyRoot", "")).resolve() != Path(history_root).resolve():
        return None
    return health


def record_url(port, record_id):
    if record_id:
        safe_id = urllib.parse.quote(record_id)
        return f"http://127.0.0.1:{port}/history/{safe_id}/index.html"
    return f"http://127.0.0.1:{port}/history/index.html"


def start_background(args, output_root, history_root, token):
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--serve",
        "--output-root",
        str(output_root),
        "--history-root",
        str(history_root),
        "--port",
        str(args.port),
        "--idle-timeout",
        str(args.idle_timeout),
        "--token",
        token,
    ]
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        creationflags = 0
    subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=(os.name != "nt"),
        creationflags=creationflags,
    )


def start_or_reuse(args):
    output_root, history_root = normalize_roots(args.output_root, args.history_root)
    path = state_path(output_root)
    existing = read_json(path, {})
    health = probe_state(existing, output_root, history_root)
    if health:
        print(f"REUSED: http://127.0.0.1:{existing['port']}")
        print(f"VIEWER: {record_url(existing['port'], args.record)}")
        return 0

    remove_file(path)
    token = secrets.token_urlsafe(24)
    start_background(args, output_root, history_root, token)
    deadline = time.time() + 8
    while time.time() < deadline:
        state = read_json(path, {})
        health = probe_state(state, output_root, history_root)
        if health:
            print(f"STARTED: http://127.0.0.1:{state['port']}")
            print(f"VIEWER: {record_url(state['port'], args.record)}")
            return 0
        time.sleep(0.1)
    print("ERROR: viewer server did not become ready", file=sys.stderr)
    return 1


def stop_server(args):
    output_root, history_root = normalize_roots(args.output_root, args.history_root)
    path = state_path(output_root)
    state = read_json(path, {})
    health = probe_state(state, output_root, history_root)
    if not health:
        remove_file(path)
        print("STOPPED: no running viewer")
        return 0
    try:
        request_json(
            shutdown_url(state["port"]),
            timeout=2,
            method="POST",
            body={"token": state["token"]},
            headers={"Content-Type": "application/json"},
        )
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        pass
    deadline = time.time() + 5
    while time.time() < deadline:
        if not probe_state(state, output_root, history_root):
            remove_file(path)
            print("STOPPED: viewer server")
            return 0
        time.sleep(0.1)
    print("ERROR: viewer server did not stop", file=sys.stderr)
    return 1


def print_status(args):
    output_root, history_root = normalize_roots(args.output_root, args.history_root)
    state = read_json(state_path(output_root), {})
    health = probe_state(state, output_root, history_root)
    if not health:
        print("STATUS: stopped")
        return 1
    print(f"STATUS: running on http://127.0.0.1:{state['port']}")
    return 0


class ViewerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, handler_class, output_root, history_root, state_file, token, idle_timeout):
        super().__init__(server_address, handler_class)
        self.output_root = Path(output_root).resolve()
        self.history_root = Path(history_root).resolve()
        self.state_file = Path(state_file)
        self.token = token
        self.idle_timeout = max(0, int(idle_timeout))
        self.last_request_at = time.time()
        self.shutdown_started = False

    def touch(self):
        self.last_request_at = time.time()


class ViewerHandler(SimpleHTTPRequestHandler):
    server_version = "RpgMeViewer/1.0"
    utf8_types = {
        ".css": "text/css; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }

    def translate_path(self, path):
        parsed = urllib.parse.urlparse(path)
        relative = urllib.parse.unquote(parsed.path).lstrip("/")
        candidate = (self.server.output_root / relative).resolve()
        try:
            candidate.relative_to(self.server.output_root)
        except ValueError:
            return str(self.server.output_root / "__forbidden__")
        return str(candidate)

    def log_message(self, format, *args):
        return

    def guess_type(self, path):
        suffix = Path(urllib.parse.urlparse(path).path).suffix.lower()
        if suffix in self.utf8_types:
            return self.utf8_types[suffix]
        return super().guess_type(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload, status=HTTPStatus.OK):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.server.touch()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            self.send_json({
                "status": "ok",
                "pid": os.getpid(),
                "port": self.server.server_port,
                "outputRoot": str(self.server.output_root),
                "historyRoot": str(self.server.history_root),
            })
            return
        if path == "/api/records":
            self.send_json(read_json(self.server.history_root / "index.json", {"records": []}))
            return
        if path.startswith("/api/records/"):
            record_id = urllib.parse.unquote(path.removeprefix("/api/records/")).strip("/")
            if "/" in record_id or "\\" in record_id or not record_id:
                self.send_json({"error": "invalid record id"}, HTTPStatus.BAD_REQUEST)
                return
            metadata_path = self.server.history_root / record_id / "metadata.json"
            if not metadata_path.is_file():
                self.send_json({"error": "record not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_json(read_json(metadata_path, {}))
            return
        super().do_GET()

    def do_POST(self):
        self.server.touch()
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/shutdown":
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
        if payload.get("token") != self.server.token:
            self.send_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            return
        self.send_json({"status": "shutting_down"})
        self.server.shutdown_started = True
        remove_file(self.server.state_file)
        threading.Thread(target=self.server.shutdown, daemon=True).start()


def idle_watcher(server):
    while not server.shutdown_started:
        if server.idle_timeout and time.time() - server.last_request_at > server.idle_timeout:
            server.shutdown_started = True
            remove_file(server.state_file)
            threading.Thread(target=server.shutdown, daemon=True).start()
            return
        time.sleep(1)


def serve(args):
    output_root, history_root = normalize_roots(args.output_root, args.history_root)
    state_file = state_path(output_root)
    token = args.token or secrets.token_urlsafe(24)
    server = ViewerServer(
        ("127.0.0.1", int(args.port)),
        ViewerHandler,
        output_root,
        history_root,
        state_file,
        token,
        args.idle_timeout,
    )

    def handle_stop(signum, frame):
        server.shutdown_started = True
        remove_file(state_file)
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, handle_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_stop)

    write_json(
        state_file,
        {
            "pid": os.getpid(),
            "port": server.server_port,
            "token": token,
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "outputRoot": str(output_root),
            "historyRoot": str(history_root),
        },
    )
    watcher = threading.Thread(target=idle_watcher, args=(server,), daemon=True)
    watcher.start()
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        remove_file(state_file)
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Run the local rpg-me history viewer.")
    parser.add_argument("--record", default="", help="Record id to open")
    parser.add_argument("--status", action="store_true", help="Check whether the viewer is running")
    parser.add_argument("--stop", action="store_true", help="Stop the running viewer")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--token", default="", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=8765, help="Local viewer port")
    parser.add_argument("--idle-timeout", type=int, default=3600, help="Stop after this many idle seconds")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Output root directory")
    parser.add_argument("--history-root", default=str(DEFAULT_HISTORY_ROOT), help="History output directory")
    args = parser.parse_args()

    if args.serve:
        serve(args)
        return 0
    if args.stop:
        return stop_server(args)
    if args.status:
        return print_status(args)
    return start_or_reuse(args)


if __name__ == "__main__":
    raise SystemExit(main())
