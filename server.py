from __future__ import annotations

import gzip
from io import BytesIO
import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent
TEXT_TYPES = {
    "application/javascript",
    "application/json",
    "image/svg+xml",
    "text/css",
    "text/html",
    "text/javascript",
    "text/plain",
    "text/xml",
}


class CacheHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def translate_path(self, path: str) -> str:
        clean_path = unquote(path.split("?", 1)[0].split("#", 1)[0])
        parts = [part for part in Path(clean_path).parts if part not in {"/", ".."}]
        return str(ROOT.joinpath(*parts))

    def end_headers(self) -> None:
        request_path = self.path.split("?", 1)[0]
        if request_path in {"/", "/index.html"}:
            self.send_header("Cache-Control", "no-cache")
        elif request_path.endswith((".css", ".js", ".json", ".png", ".webp", ".jpg", ".jpeg", ".svg", ".ico")):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send_head(self):
        path = Path(self.translate_path(self.path))
        if path.is_dir():
            path = path / "index.html"
        if not path.exists() or not path.is_file():
            self.send_error(404, "File not found")
            return None

        content_type = self.guess_type(str(path))
        accepts_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
        body = path.read_bytes()
        use_gzip = accepts_gzip and content_type.split(";")[0] in TEXT_TYPES
        if use_gzip:
            body = gzip.compress(body, compresslevel=9)

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Last-Modified", self.date_time_string(path.stat().st_mtime))
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.end_headers()
        return BytesIO(body)

    def copyfile(self, source, outputfile) -> None:
        outputfile.write(source.read())


if __name__ == "__main__":
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("image/webp", ".webp")
    server = ThreadingHTTPServer(("0.0.0.0", 8000), CacheHandler)
    print("Serving Iliamo on http://localhost:8000/")
    server.serve_forever()
