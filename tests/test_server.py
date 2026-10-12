"""The docs server: nothing without the login, the site with it."""

import gzip
from base64 import b64encode

import pytest

import server

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def site(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<h1>Home</h1>")
    (tmp_path / "404.html").write_text("<h1>Missing</h1>")
    (tmp_path / "business" / "FINANCE").mkdir(parents=True)
    (tmp_path / "business" / "FINANCE" / "index.html").write_text("<h1>Finance</h1>" + "x" * 2000)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path.parent / "secret.txt").write_text("outside the site")
    monkeypatch.setattr(server, "ROOT", tmp_path.resolve())
    return tmp_path


def call(app, path="/", auth=None, method="GET", client="203.0.113.7", encoding=""):
    environ = {"PATH_INFO": path, "REQUEST_METHOD": method, "HTTP_X_FORWARDED_FOR": f"{client}, 10.0.0.1", "HTTP_ACCEPT_ENCODING": encoding}
    if auth:
        environ["HTTP_AUTHORIZATION"] = "Basic " + b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    seen = {}

    def start_response(status, headers):
        seen["status"], seen["headers"] = status, dict(headers)

    body = b"".join(app(environ, start_response))
    return int(seen["status"][:3]), seen["headers"], body


GOOD = ("fidelia", PASSWORD)


def test_every_page_needs_the_login(site):
    app = server.make_app(*GOOD)
    for path in ("/", "/business/FINANCE/", "/assets/app.js", "/missing"):
        status, headers, body = call(app, path)
        assert status == 401 and "Finance" not in body.decode()
        assert headers["WWW-Authenticate"].startswith("Basic realm=")
    assert call(app, "/", auth=("fidelia", "wrong-password-wrong"))[0] == 401
    assert call(app, "/", auth=("someone", PASSWORD))[0] == 401


def test_the_login_serves_the_site(site):
    app = server.make_app(*GOOD)
    status, headers, body = call(app, "/business/FINANCE/", auth=GOOD)
    assert status == 200 and b"Finance" in body
    assert headers["Content-Type"].startswith("text/html")
    assert headers["X-Robots-Tag"] == "noindex, nofollow" and headers["Cache-Control"] == "private, no-cache"
    assert call(app, "/assets/app.js", auth=GOOD)[1]["Cache-Control"] == "private, max-age=86400"


def test_a_directory_without_its_slash_is_redirected(site):
    status, headers, _ = call(server.make_app(*GOOD), "/business/FINANCE", auth=GOOD)
    assert status == 301 and headers["Location"] == "/business/FINANCE/"


def test_unknown_pages_and_escapes_get_the_404_page(site):
    app = server.make_app(*GOOD)
    status, _, body = call(app, "/nope/", auth=GOOD)
    assert status == 404 and b"Missing" in body
    status, _, body = call(app, "/../secret.txt", auth=GOOD)
    assert status == 404 and b"outside" not in body


def test_text_is_gzipped_when_the_browser_accepts_it(site):
    status, headers, body = call(server.make_app(*GOOD), "/business/FINANCE/", auth=GOOD, encoding="gzip, br")
    assert status == 200 and headers["Content-Encoding"] == "gzip"
    assert gzip.decompress(body).startswith(b"<h1>Finance</h1>")
    assert int(headers["Content-Length"]) == len(body)


def test_head_and_other_methods(site):
    app = server.make_app(*GOOD)
    status, headers, body = call(app, "/", auth=GOOD, method="HEAD")
    assert status == 200 and body == b"" and int(headers["Content-Length"]) > 0
    assert call(app, "/", auth=GOOD, method="POST")[0] == 405


def test_repeated_wrong_logins_are_slowed_down(site):
    clock = [0.0]
    failures = server.Failures(limit=3, window=60, clock=lambda: clock[0])
    app = server.make_app(*GOOD, failures=failures)
    for _ in range(3):
        assert call(app, "/", auth=("fidelia", "nope"))[0] == 401
    # Blocked even with the right password, but only for that address.
    assert call(app, "/", auth=GOOD)[0] == 429
    assert call(app, "/", auth=GOOD, client="198.51.100.2")[0] == 200
    clock[0] = 61
    assert call(app, "/", auth=GOOD)[0] == 200


def test_health_check_needs_no_login_and_shows_nothing(site):
    status, _, body = call(server.make_app(*GOOD), "/healthz")
    assert status == 200 and body == b"ok"


def test_refuses_to_start_without_a_strong_password(site, monkeypatch):
    monkeypatch.setenv("DOCS_PASSWORD", "short")
    with pytest.raises(SystemExit, match="DOCS_PASSWORD"):
        server.main()
    monkeypatch.delenv("DOCS_PASSWORD")
    with pytest.raises(SystemExit, match="DOCS_PASSWORD"):
        server.main()
