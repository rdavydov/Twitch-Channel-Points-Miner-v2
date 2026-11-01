"""Loopback-only Flask application with a single observational POST action."""

import hmac
import math
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, request, send_file, send_from_directory
from waitress import create_server


def create_app(service, static_folder=None):
    folder = Path(static_folder or Path(__file__).parent / "static").resolve()
    app = Flask(__name__, static_folder=None)
    csrf = secrets.token_urlsafe(32)
    app.config.update(MAX_CONTENT_LENGTH=1024, TESTING=False)

    @app.before_request
    def local_only():
        host = urlsplit("http://" + request.host).hostname
        if host not in {"127.0.0.1", "localhost", "::1"} or request.remote_addr not in {
            "127.0.0.1",
            "::1",
            None,
        }:
            abort(403)
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            abort(403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.path != "/api/v1/refresh" or request.method != "POST":
                abort(405)
            if origin != request.host_url.rstrip("/") or not hmac.compare_digest(
                request.headers.get("X-CSRF-Token", ""), csrf
            ):
                abort(403)

    @app.after_request
    def headers(response):
        response.headers[
            "Content-Security-Policy"
        ] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/api/") or request.path == "/":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        if not (folder / "index.html").is_file():
            return (
                "Dashboard assets are missing. Build the frontend as described in README.md.",
                503,
            )
        return send_from_directory(folder, "index.html")

    @app.get("/assets/<path:name>")
    def assets(name):
        return send_from_directory(folder / "assets", name, max_age=604800)

    @app.get("/api/v1/bootstrap")
    def bootstrap():
        return jsonify(
            account=service.account,
            csrf_token=csrf,
            timezone=service.settings.timezone,
            read_only=True,
            snapshot=service.snapshot(),
        )

    @app.get("/api/v1/snapshot")
    def snapshot():
        return jsonify(service.snapshot())

    @app.get("/api/v1/refresh")
    def refresh_state():
        return jsonify(service.refresh_status())

    @app.post("/api/v1/refresh")
    def refresh():
        return jsonify(service.request_refresh()), 202

    def number(name, default):
        try:
            result = float(request.args.get(name, default))
            if not math.isfinite(result):
                raise ValueError()
            return result
        except (TypeError, ValueError):
            abort(400)

    @app.get("/api/v1/history/<channel>")
    def history(channel):
        known = {r["channel"] for r in service.snapshot().get("channels", [])}
        if channel not in known:
            abort(404)
        start, end = number("start", service.clock() - 7 * 86400), number(
            "end", service.clock()
        )
        if start > end:
            abort(400)
        return jsonify(service.store.history(channel, start, end))

    @app.get("/api/v1/activity")
    def activity():
        return jsonify(
            service.store.events(
                channel=request.args.get("channel"),
                start=number("start", 0),
                end=number("end", service.clock()),
                search=request.args.get("search", ""),
            )
        )

    @app.get("/api/v1/logs")
    def logs():
        return jsonify(
            service.logs(
                request.args.get("cursor", ""), request.args.get("debug") == "true"
            )
        )

    def reports():
        base = Path("logs/reports").resolve()
        # Serve only miner-generated report names for this account.
        return {
            str(p.relative_to(base)).replace("\\", "/"): p
            for p in base.rglob("*")
            if p.is_file()
            and p.suffix in {".xlsx", ".csv"}
            and service.account in p.stem
            and base in p.resolve().parents
        }

    @app.get("/api/v1/reports")
    def report_list():
        return jsonify(
            [
                dict(
                    id=name,
                    name=path.name,
                    modified_at=path.stat().st_mtime,
                    bytes=path.stat().st_size,
                )
                for name, path in sorted(reports().items(), reverse=True)
            ][:365]
        )

    @app.get("/api/v1/reports/<path:name>")
    def report(name):
        path = reports().get(name)
        if path is None:
            abort(404)
        return send_file(path, as_attachment=True)

    return app


def start_server(service):
    server = create_server(
        create_app(service),
        host=service.settings.host,
        port=service.settings.port,
        threads=4,
        clear_untrusted_proxy_headers=True,
    )
    service.server = server
    import threading

    thread = threading.Thread(target=server.run, name="Dashboard HTTP", daemon=True)
    thread.start()
    return server
