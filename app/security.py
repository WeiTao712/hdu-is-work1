"""Authentication primitives: password hashing, JWT issuing and verification.

Design notes
------------
* Passwords are hashed with **bcrypt** (adaptive, salted, deliberately slow).
  SHA-256 is *not* acceptable: it is fast, unsalted and therefore trivial to
  brute-force with a GPU.
* Access tokens are short-lived (15 min) JWTs signed with HS256.  The token
  contains only non-sensitive claims (subject, username, issue/expiry, jti).
* Every protected endpoint goes through :func:`token_required`, which checks
  the signature, the issuer, the audience, the expiry and the revocation list.
"""

from __future__ import annotations

import functools
import hmac
import re
import secrets
import threading
import time
from typing import Any, Callable

import bcrypt
import jwt
from flask import current_app, g, jsonify, request

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")

# A tiny in-process revocation list.  A production deployment would keep this
# in Redis so that it survives restarts and is shared between workers.
_REVOKED_JTIS: dict[str, float] = {}
_REVOKED_LOCK = threading.Lock()


class AuthError(Exception):
    """Raised when a credential or a token is not acceptable."""

    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.message = message
        self.status = status


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def hash_password(password: str, rounds: int | None = None) -> str:
    rounds = rounds or current_app.config["BCRYPT_ROUNDS"]
    # bcrypt silently truncates at 72 bytes -> reject longer values up front.
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 bytes")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash in the database -> treat as "no match", never crash.
        return False


def password_problems(password: str) -> list[str]:
    """Return a list of human readable policy violations (empty == accepted)."""
    problems: list[str] = []
    minimum = current_app.config["PASSWORD_MIN_LENGTH"]
    if len(password) < minimum:
        problems.append(f"Password must be at least {minimum} characters long")
    if len(password.encode("utf-8")) > 72:
        problems.append("Password must not exceed 72 bytes")
    if password.lower() in {"password", "123456789012", "qwerty123456"}:
        problems.append("Password is too common")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        problems.append("Password must contain both letters and digits")
    return problems


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def issue_token(user_id: int, username: str) -> tuple[str, int]:
    now = int(time.time())
    ttl = int(current_app.config["ACCESS_TOKEN_TTL"])
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
        "jti": secrets.token_urlsafe(16),
        "iss": current_app.config["JWT_ISSUER"],
        "aud": current_app.config["JWT_AUDIENCE"],
    }
    token = jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"])
    if isinstance(token, bytes):  # PyJWT < 2.0 compatibility
        token = token.decode("utf-8")
    return token, ttl


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            # ``algorithms`` is a fixed allow-list: this is what prevents the
            # classic "alg: none" and RS256->HS256 key-confusion attacks.
            algorithms=[current_app.config["JWT_ALGORITHM"]],
            audience=current_app.config["JWT_AUDIENCE"],
            issuer=current_app.config["JWT_ISSUER"],
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthError("Invalid token")
    if is_revoked(payload.get("jti", "")):
        raise AuthError("Token has been revoked")
    return payload


def revoke(jti: str, exp: int | None = None) -> None:
    with _REVOKED_LOCK:
        _REVOKED_JTIS[jti] = float(exp or time.time() + 3600)
        # opportunistic cleanup so the set cannot grow without bound
        now = time.time()
        for key in [k for k, v in _REVOKED_JTIS.items() if v < now]:
            _REVOKED_JTIS.pop(key, None)


def is_revoked(jti: str) -> bool:
    with _REVOKED_LOCK:
        return jti in _REVOKED_JTIS


def clear_revocations() -> None:
    with _REVOKED_LOCK:
        _REVOKED_JTIS.clear()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

def _extract_bearer() -> str | None:
    header = request.headers.get("Authorization", "")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def token_required(view: Callable[..., Any]) -> Callable[..., Any]:
    """Reject any request that does not carry a valid, non-revoked token."""

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        token = _extract_bearer()
        if not token:
            return jsonify(error="authentication_required",
                           message="A Bearer token is required for this endpoint",
                           status=401), 401
        try:
            payload = decode_token(token)
        except AuthError as exc:
            return jsonify(error="invalid_token", message=exc.message, status=exc.status), exc.status
        g.token_claims = payload
        g.current_user = {"id": int(payload["sub"]), "username": payload.get("username", "")}
        return view(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Brute-force protection (per username + per client address)
# ---------------------------------------------------------------------------

_ATTEMPTS: dict[str, list[float]] = {}
_ATTEMPTS_LOCK = threading.Lock()


def _keys_for(username: str) -> list[str]:
    remote = request.remote_addr or "unknown"
    return [f"user:{username.lower()}", f"ip:{remote}"]


def login_allowed(username: str) -> bool:
    window = current_app.config["LOGIN_WINDOW_SECONDS"]
    limit = current_app.config["LOGIN_MAX_ATTEMPTS"]
    now = time.time()
    with _ATTEMPTS_LOCK:
        for key in _keys_for(username):
            hits = [t for t in _ATTEMPTS.get(key, []) if now - t < window]
            _ATTEMPTS[key] = hits
            if len(hits) >= limit:
                return False
    return True


def register_failed_attempt(username: str) -> None:
    now = time.time()
    with _ATTEMPTS_LOCK:
        for key in _keys_for(username):
            _ATTEMPTS.setdefault(key, []).append(now)


def reset_attempts(username: str) -> None:
    with _ATTEMPTS_LOCK:
        for key in _keys_for(username):
            _ATTEMPTS.pop(key, None)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
