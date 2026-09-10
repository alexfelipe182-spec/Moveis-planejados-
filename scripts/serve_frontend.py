"""Development/test server only; production uses frontend_server:app with Uvicorn."""

import argparse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlsplit


FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
PRIVATE_ROOTS = {".git", "backend", "scripts", "tests"}
PRIVATE_SUFFIXES = {".cjs", ".py", ".pyc"}


class FrontendHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def send_head(self):
        path = unquote(urlsplit(self.path).path)
        if path == "/health":
            body = b"ok"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return BytesIO(body)

        parts = tuple(part for part in path.split("/") if part)
        target = (FRONTEND / Path(*parts)).resolve()
        unsafe = (
            any(part in {".", ".."} or part.startswith(".") for part in parts)
            or (parts and parts[0].lower() in PRIVATE_ROOTS)
            or target.suffix.lower() in PRIVATE_SUFFIXES
        )
        try:
            target.relative_to(FRONTEND.resolve())
        except ValueError:
            unsafe = True

        if unsafe or ((path.startswith(("/api/", "/assets/")) or target.suffix) and not target.is_file()):
            self.send_error(HTTPStatus.NOT_FOUND)
            return None
        if not target.is_file():
            self.path = "/index.html"
        return super().send_head()


def main():
    parser = argparse.ArgumentParser(description="Serve the frontend with SPA fallback")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), FrontendHandler)
    print(f"Frontend disponível em http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
