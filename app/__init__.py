"""Application factory."""

from __future__ import annotations

import os

from flask import Flask, jsonify

from .config import Config
from .db import close_db, connect, init_schema
from .errors import register_error_handlers
from .security import hash_password


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    app.teardown_appcontext(close_db)
    register_error_handlers(app)

    from .routes.auth import bp as auth_bp
    from .routes.posts import bp as data_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(data_bp)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.after_request
    def security_headers(response):
        # Never let a browser "sniff" JSON as HTML, never embed the app in a
        # frame, never leak the full URL to third parties.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    _bootstrap_database(app)
    return app


def _bootstrap_database(app: Flask) -> None:
    path = app.config["DATABASE_PATH"]
    if path != ":memory:":
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    conn = connect(path)
    try:
        init_schema(conn)
        if app.config.get("SEED_DEMO_DATA", True):
            _seed(conn, app.config["BCRYPT_ROUNDS"])
    finally:
        conn.close()


def _seed(conn, rounds: int) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing:
        return
    demo_hash = hash_password("DemoPassw0rd!2024", rounds=rounds)
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
        ("demo", demo_hash, "Demo User"),
    )
    demo_id = int(cur.lastrowid)
    posts = [
        (demo_id, "Welcome to the HDU IS Work 1 API",
         "This endpoint is protected by a JWT. Try it without a token and you get a 401."),
        (demo_id, "Parameterised queries",
         "Every SQL statement in this project binds its arguments, so ' OR 1=1 -- stays a literal string."),
        (demo_id, "Stored XSS is neutralised on output",
         "The /preview endpoint escapes every user controlled value before it reaches the DOM."),
    ]
    conn.executemany(
        "INSERT INTO posts (author_id, title, body) VALUES (?, ?, ?)",
        posts,
    )
    conn.commit()
