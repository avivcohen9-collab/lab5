"""One local game, served with Python's standard library."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from session import Session

STATIC = Path(__file__).parent / "static"


def make_server(port=8000):
    session = Session()

    class Handler(BaseHTTPRequestHandler):
        def respond(self, code, body, content_type):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, code, value):
            self.respond(code, json.dumps(value).encode(), "application/json")

        def do_GET(self):
            if self.path == "/api/state":
                self.send_json(200, session.view())
                return
            routes = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }
            if self.path not in routes:
                self.send_json(404, {"error": "Not found"})
                return
            name, content_type = routes[self.path]
            self.respond(200, (STATIC / name).read_bytes(), content_type)

        def do_POST(self):
            if self.path != "/api/action":
                self.send_json(404, {"error": "Not found"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1_000_000:
                    raise ValueError("Invalid request size")
                action = json.loads(self.rfile.read(size))
                if not isinstance(action, dict):
                    raise TypeError("Expected an action object")
                result = session.dispatch(action)
            except (ValueError, TypeError) as error:
                self.send_json(400, {"error": str(error)})
                return
            self.send_json(200, result)

    return HTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f"Open http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
