import argparse
import base64
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
PNG_B64 = base64.b64encode(PNG_BYTES).decode("ascii")


class Handler(BaseHTTPRequestHandler):
    state_path = Path()
    state_lock = Lock()
    request_count = 0

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else b""
        with Handler.state_lock:
            Handler.request_count += 1
            state = {
                "ready": True,
                "port": self.server.server_address[1],
                "request_count": Handler.request_count,
                "last_path": self.path,
                "last_content_type": self.headers.get("Content-Type", ""),
                "last_body_bytes": len(body),
            }
            Handler.state_path.write_text(json.dumps(state), encoding="utf-8")
        response = json.dumps({"data": [{"b64_json": PNG_B64}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, _format, *_args):
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    args = parser.parse_args()
    Handler.state_path = Path(args.state).resolve()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Handler.state_path.write_text(
        json.dumps({"ready": True, "port": server.server_address[1], "request_count": 0}),
        encoding="utf-8",
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
