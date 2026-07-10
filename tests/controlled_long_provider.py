import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    delay_seconds = 120
    state_path = Path()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length:
            self.rfile.read(content_length)
        Handler.state_path.write_text(
            json.dumps({"request_received": True, "path": self.path}),
            encoding="utf-8",
        )
        time.sleep(Handler.delay_seconds)
        body = json.dumps({"data": []}).encode("utf-8")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, _format, *_args):
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--delay", type=int, default=120)
    args = parser.parse_args()
    Handler.state_path = Path(args.state).resolve()
    Handler.delay_seconds = args.delay
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Handler.state_path.write_text(
        json.dumps({"ready": True, "port": server.server_address[1]}),
        encoding="utf-8",
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
