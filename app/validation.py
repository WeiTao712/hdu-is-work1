"""Input validation helpers.

Validation happens *before* anything touches the database.  It is a
defence-in-depth measure: parameterised queries already make SQL injection
impossible, but strict validation also blocks malformed data from ever being
stored and later rendered.
"""

from __future__ import annotations

import re
from typing import Any

from flask import Request

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ValidationError(Exception):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def require_json(request: Request) -> dict[str, Any]:
    if not request.is_json:
        raise ValidationError("body", "Content-Type must be application/json")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("body", "Request body must be a JSON object")
    return payload


def _string(payload: dict[str, Any], field: str, *, min_len: int = 1, max_len: int, strip: bool = True) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise ValidationError(field, f"'{field}' must be a string")
    if strip:
        value = value.strip()
    if len(value) < min_len:
        raise ValidationError(field, f"'{field}' must not be empty")
    if len(value) > max_len:
        raise ValidationError(field, f"'{field}' must be at most {max_len} characters")
    if CONTROL_CHARS_RE.search(value):
        raise ValidationError(field, f"'{field}' contains control characters")
    return value


def username(payload: dict[str, Any], field: str = "username") -> str:
    value = _string(payload, field, max_len=32)
    if not USERNAME_RE.match(value):
        raise ValidationError(field, "Username must be 3-32 characters: letters, digits or underscore")
    return value


def password(payload: dict[str, Any], field: str = "password") -> str:
    # Never strip or normalise a password -- that silently changes it.
    return _string(payload, field, max_len=72, strip=False)


def display_name(payload: dict[str, Any], field: str = "display_name") -> str:
    return _string(payload, field, max_len=64)


def post_title(payload: dict[str, Any], field: str = "title") -> str:
    return _string(payload, field, max_len=120)


def post_body(payload: dict[str, Any], field: str = "body") -> str:
    return _string(payload, field, max_len=2000)


def search_term(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    if len(raw) > 100:
        raise ValidationError("q", "'q' must be at most 100 characters")
    return raw
