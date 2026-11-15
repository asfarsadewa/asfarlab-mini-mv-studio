# Serves the review canvas on this machine only. It saves notes to mvs/<film>/review/notes.json,
# and lyric reviews from tools/review/lyrics.html to mvs/<film>/review/lyrics.json.
# Usage: python tools/review_server.py [port]
import json, os, re, sys, threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5350


NOTES_LOCK = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(302)
            self.send_header("Location", "/tools/review/index.html")
            self.end_headers()
            return
        if self.path == "/api/films":
            films = sorted(p.parent.name for p in (ROOT / "mvs").glob("*/brief.json"))
            body = json.dumps(films).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        match = re.fullmatch(r"/api/(notes|lyrics)/([a-z0-9_-]+)", self.path)
        if not match or not (ROOT / "mvs" / match.group(2)).is_dir():
            self.send_error(404)
            return
        kind, film = match.groups()
        try:
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        except (TypeError, ValueError):
            self.send_error(400)
            return
        # Notes are a list. A lyric review is an object.
        if not isinstance(data, list if kind == "notes" else dict):
            self.send_error(400)
            return
        folder = ROOT / "mvs" / film / "review"
        folder.mkdir(exist_ok=True)
        # The rename is atomic, so a crash or a second request cannot leave half a file.
        with NOTES_LOCK:
            temp = folder / f"{kind}.json.tmp"
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, folder / f"{kind}.json")
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(ROOT)))
print(f"Review canvas: http://127.0.0.1:{PORT}/", flush=True)
server.serve_forever()
