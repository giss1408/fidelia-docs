"""Serves the built documentation (site/) behind one shared login.

The docs hold internal and confidential pages (finance, investor readiness,
partner drafts), and a Render static site cannot ask for a password, so the
site runs as a small web service instead (render.yaml):

    mkdocs build --strict      # writes site/
    python server.py           # serves it on $PORT

HTTP basic auth over Render's HTTPS, with the login in DOCS_USERNAME and
DOCS_PASSWORD. It fails closed: without a password of at least 16 characters
the server refuses to start rather than serve the docs to anyone. Repeated
wrong passwords from one address are slowed down with a 429.

/healthz answers without a login, for Render's health check; it reveals nothing.
"""

import gzip
import hmac
import mimetypes
import os
import sys
import threading
import time
from base64 import b64decode
from functools import lru_cache
from pathlib import Path

ROOT = Path(os.getenv("DOCS_SITE_DIR", Path(__file__).resolve().parent / "site")).resolve()
REALM = "Fidelia documentation"
MIN_PASSWORD = 16
# Failed logins per address before refusing, and the window they are counted in.
MAX_FAILURES = 10
FAILURE_WINDOW_S = 600
COMPRESSIBLE = ("text/", "application/javascript", "application/json", "image/svg+xml", "application/xml")

HEADERS = [
    ("X-Robots-Tag", "noindex, nofollow"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Strict-Transport-Security", "max-age=31536000"),
]

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/json", ".json")


class Failures:
    """Wrong logins per client address, in a sliding window. In memory: one
    instance serves the docs, and a restart forgetting them is acceptable."""

    def __init__(self, limit=MAX_FAILURES, window=FAILURE_WINDOW_S, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.seen: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    def _recent(self, client: str) -> list[float]:
        now = self.clock()
        recent = [t for t in self.seen.get(client, []) if now - t < self.window]
        if recent:
            self.seen[client] = recent
        else:
            self.seen.pop(client, None)
        return recent

    def blocked(self, client: str) -> bool:
        with self.lock:
            return len(self._recent(client)) >= self.limit

    def add(self, client: str) -> None:
        with self.lock:
            self.seen[client] = self._recent(client) + [self.clock()]


def _client(environ) -> str:
    # Render's proxy puts the visitor's address first in X-Forwarded-For.
    forwarded = environ.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() or environ.get("REMOTE_ADDR", "?")


def _authorized(environ, username: str, password: str) -> bool:
    header = environ.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Basic "):
        return False
    try:
        given_user, _, given_password = b64decode(header[6:]).decode("utf-8").partition(":")
    except (ValueError, UnicodeDecodeError):
        return False
    # Both compared, always, in constant time: no early exit to time.
    user_ok = hmac.compare_digest(given_user.encode(), username.encode())
    password_ok = hmac.compare_digest(given_password.encode(), password.encode())
    return user_ok and password_ok


def _resolve(path: str) -> Path | None:
    """The file a URL path names inside ROOT, or None. MkDocs writes
    `page/index.html` for `page/`, so a directory serves its index."""
    target = (ROOT / path.lstrip("/")).resolve()
    if target != ROOT and ROOT not in target.parents:
        return None
    if target.is_dir():
        target = target / "index.html"
    return target if target.is_file() else None


@lru_cache(maxsize=256)
def _gzipped(path: Path, mtime_ns: int) -> bytes:
    return gzip.compress(path.read_bytes(), compresslevel=6, mtime=0)


def _cache_control(path: str) -> str:
    # Authenticated content: never in a shared cache. Assets change rarely;
    # pages must show the latest deploy.
    return "private, max-age=86400" if "/assets/" in path else "private, no-cache"


def make_app(username: str, password: str, failures: Failures | None = None):
    failures = failures or Failures()

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/") or "/"
        method = environ.get("REQUEST_METHOD", "GET")

        if path == "/healthz":
            start_response("200 OK", [("Content-Type", "text/plain"), ("Cache-Control", "no-store")])
            return [b"ok"]

        if method not in ("GET", "HEAD"):
            start_response("405 Method Not Allowed", [("Allow", "GET, HEAD"), ("Content-Length", "0"), *HEADERS])
            return [b""]

        client = _client(environ)
        if failures.blocked(client):
            start_response("429 Too Many Requests", [("Retry-After", str(FAILURE_WINDOW_S)), ("Content-Type", "text/plain"), *HEADERS])
            return [b"Too many attempts. Try again later."]
        if not _authorized(environ, username, password):
            if environ.get("HTTP_AUTHORIZATION"):
                failures.add(client)
            start_response("401 Unauthorized", [
                ("WWW-Authenticate", f'Basic realm="{REALM}", charset="UTF-8"'),
                ("Content-Type", "text/plain; charset=utf-8"), ("Cache-Control", "no-store"), *HEADERS,
            ])
            return [b"Login required."]

        # `page` without its slash: send the browser to `page/`, so the page's
        # relative links resolve as MkDocs wrote them.
        if not path.endswith("/") and (ROOT / path.lstrip("/")).resolve().is_dir() and _resolve(path):
            query = environ.get("QUERY_STRING")
            start_response("301 Moved Permanently", [("Location", path + "/" + (f"?{query}" if query else "")), *HEADERS])
            return [b""]

        status, target = "200 OK", _resolve(path)
        if target is None:
            status, target = "404 Not Found", _resolve("/404.html")
            if target is None:
                start_response(status, [("Content-Type", "text/plain"), *HEADERS])
                return [b"Not found."]

        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
            ctype += "; charset=utf-8"
        headers = [("Content-Type", ctype), ("Cache-Control", _cache_control(path)), ("Vary", "Accept-Encoding"), *HEADERS]
        if ctype.startswith(COMPRESSIBLE) and "gzip" in environ.get("HTTP_ACCEPT_ENCODING", ""):
            body = _gzipped(target, target.stat().st_mtime_ns)
            headers.append(("Content-Encoding", "gzip"))
        else:
            body = target.read_bytes()
        headers.append(("Content-Length", str(len(body))))
        start_response(status, headers)
        return [b"" if method == "HEAD" else body]

    return app


def main() -> None:
    username = os.getenv("DOCS_USERNAME", "fidelia")
    password = os.getenv("DOCS_PASSWORD", "")
    if len(password) < MIN_PASSWORD:
        sys.exit(f"DOCS_PASSWORD must be set to at least {MIN_PASSWORD} characters; refusing to serve the docs without it.")
    if not (ROOT / "index.html").is_file():
        sys.exit(f"No built site in {ROOT}: run `mkdocs build` first.")
    from waitress import serve

    serve(make_app(username, password), host="0.0.0.0", port=int(os.getenv("PORT", "8000")), threads=8, ident="")


if __name__ == "__main__":
    main()
