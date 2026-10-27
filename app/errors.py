"""JSON error handling -- no stack traces, no internal details, ever."""

from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .validation import ValidationError


def _json(error: str, status: int, **extra):
    """Build a JSON error response.

    ``extra`` carries optional details (``field``, ``message``); the parameters
    here are named ``error``/``status`` so they can never collide with them.
    """
    payload = {"error": error, "status": status}
    payload.update(extra)
    return jsonify(payload), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def handle_validation_error(exc: ValidationError):
        return _json("validation_error", 400, field=exc.field, message=exc.message)

    @app.errorhandler(400)
    def handle_bad_request(_exc):
        return _json("bad_request", 400)

    @app.errorhandler(401)
    def handle_unauthorized(_exc):
        return _json("authentication_required", 401)

    @app.errorhandler(403)
    def handle_forbidden(_exc):
        return _json("forbidden", 403)

    @app.errorhandler(404)
    def handle_not_found(_exc):
        return _json("not_found", 404)

    @app.errorhandler(405)
    def handle_method_not_allowed(_exc):
        return _json("method_not_allowed", 405)

    @app.errorhandler(413)
    def handle_payload_too_large(_exc):
        return _json("payload_too_large", 413)

    @app.errorhandler(429)
    def handle_too_many_requests(_exc):
        return _json("too_many_requests", 429)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return _json(exc.name.lower().replace(" ", "_"), exc.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):  # pragma: no cover - safety net
        app.logger.exception("unhandled error: %s", exc)
        # The traceback goes to the server log, never to the client.
        return _json("internal_server_error", 500)
