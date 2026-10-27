"""Authentication endpoints: register, login, logout."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from ..db import create_user, find_user_by_username, get_db
from ..security import (
    hash_password,
    issue_token,
    login_allowed,
    password_problems,
    register_failed_attempt,
    reset_attempts,
    revoke,
    token_required,
    verify_password,
)
from ..validation import display_name, password, require_json, username

bp = Blueprint("auth", __name__, url_prefix="/auth")

# A single generic message: it must not reveal whether the username exists.
INVALID_CREDENTIALS = "Invalid username or password"


@bp.post("/register")
def register():
    payload = require_json(request)
    name = username(payload)
    pwd = password(payload)
    shown = display_name(payload)

    problems = password_problems(pwd)
    if problems:
        return jsonify(error="weak_password", status=400, message="; ".join(problems)), 400

    conn = get_db()
    if find_user_by_username(conn, name) is not None:
        return jsonify(error="conflict", status=409, message="Username already taken"), 409

    user_id = create_user(conn, name, hash_password(pwd), shown)
    return jsonify(id=user_id, username=name, display_name=shown), 201


@bp.post("/login")
def login():
    payload = require_json(request)
    name = payload.get("username")
    pwd = payload.get("password")
    if not isinstance(name, str) or not isinstance(pwd, str):
        return jsonify(error="validation_error", status=400,
                       message="'username' and 'password' are required strings"), 400

    if not login_allowed(name):
        # 429 + Retry-After: slows down credential stuffing dramatically.
        return jsonify(error="too_many_requests", status=429,
                       message="Too many failed attempts, try again later"), 429, {"Retry-After": "300"}

    conn = get_db()
    row = find_user_by_username(conn, name)
    if row is None:
        # Still run a hash comparison so that response time does not leak
        # whether the account exists (user-enumeration defence).
        verify_password(pwd, "$2b$12$" + "x" * 53)
        register_failed_attempt(name)
        return jsonify(error="invalid_credentials", status=401, message=INVALID_CREDENTIALS), 401

    if not verify_password(pwd, row["password_hash"]):
        register_failed_attempt(name)
        return jsonify(error="invalid_credentials", status=401, message=INVALID_CREDENTIALS), 401

    reset_attempts(name)
    token, ttl = issue_token(int(row["id"]), row["username"])
    return jsonify(access_token=token, token_type="Bearer", expires_in=ttl)


@bp.post("/logout")
@token_required
def logout():
    claims = g.token_claims
    revoke(claims["jti"], claims.get("exp"))
    return jsonify(message="Token revoked"), 200
