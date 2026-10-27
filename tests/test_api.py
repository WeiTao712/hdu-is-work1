"""Functional and security tests for the Work 1 API.

The suite is written so that it doubles as *evidence*: each test maps to one
requirement of the assignment (functional endpoint, SQLi, XSS, authentication).
"""

from __future__ import annotations

import base64
import json
import time

import jwt


# ---------------------------------------------------------------------------
# Functional behaviour
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_login_returns_bearer_token(client):
    resp = client.post("/auth/login", json={"username": "demo", "password": "DemoPassw0rd!2024"})
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 900
    assert body["access_token"].count(".") == 2  # three JWT segments


def test_login_rejects_wrong_password_with_generic_message(client):
    resp = client.post("/auth/login", json={"username": "demo", "password": "WrongPassword123"})
    assert resp.status_code == 401
    assert resp.get_json()["message"] == "Invalid username or password"


def test_login_does_not_leak_user_existence(client):
    wrong_pw = client.post("/auth/login", json={"username": "demo", "password": "WrongPassword123"})
    no_user = client.post("/auth/login", json={"username": "ghost", "password": "WrongPassword123"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.get_json()["message"] == no_user.get_json()["message"]


def test_data_requires_token(client):
    resp = client.get("/api/data")
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "authentication_required"


def test_data_returns_items_with_token(client, auth):
    resp = client.get("/api/data", headers=auth)
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["count"] >= 3
    assert {"id", "title", "body", "author"} <= set(body["items"][0])


def test_create_post_appears_in_list(client, auth):
    created = client.post(
        "/api/posts",
        headers=auth,
        json={"title": "Regression note", "body": "written by the test suite"},
    )
    assert created.status_code == 201
    post_id = created.get_json()["id"]

    listed = client.get("/api/data?q=Regression", headers=auth).get_json()
    assert any(item["id"] == post_id for item in listed["items"])


def test_search_is_case_insensitive_and_bounded(client, auth):
    hits = client.get("/api/data?q=PARAMETERISED", headers=auth).get_json()
    assert hits["count"] == 1


# ---------------------------------------------------------------------------
# SQL injection
# ---------------------------------------------------------------------------

def test_search_sqli_payload_is_treated_as_literal(client, auth):
    payload = "' OR 1=1 --"
    resp = client.get("/api/data", headers=auth, query_string={"q": payload})
    body = resp.get_json()
    assert resp.status_code == 200
    # A successful injection would return every row (count >= 3).  Here the
    # payload only matches the one seeded post that literally quotes it.
    assert body["count"] == 1
    assert payload in body["items"][0]["body"]
    assert payload in body["items"][0]["title"] or payload in body["items"][0]["body"]


def test_search_wildcard_is_escaped(client, auth):
    # '%' must match the literal character, not "anything"
    hits = client.get("/api/data?q=%25", headers=auth).get_json()
    assert hits["count"] == 0


def test_login_sqli_payload_does_not_authenticate(client):
    resp = client.post(
        "/auth/login",
        json={"username": "admin' OR '1'='1' --", "password": "anything"},
    )
    assert resp.status_code == 401
    assert "access_token" not in resp.get_json()


def test_union_based_payload_does_not_leak_hashes(client, auth):
    payload = "' UNION SELECT id, username, password_hash, created_at FROM users --"
    body = client.get("/api/data", headers=auth, query_string={"q": payload}).get_json()
    assert body["count"] == 0
    assert "password_hash" not in json.dumps(body)


# ---------------------------------------------------------------------------
# XSS
# ---------------------------------------------------------------------------

def test_stored_xss_is_escaped_in_preview(client, auth):
    payload = "<script>alert('xss')</script>"
    created = client.post("/api/posts", headers=auth, json={"title": payload, "body": payload})
    assert created.status_code == 201
    post_id = created.get_json()["id"]

    resp = client.get(f"/api/posts/{post_id}/preview", headers=auth)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html
    assert "Content-Security-Policy" in resp.headers


def test_json_responses_are_not_sniffable(client, auth):
    resp = client.get("/api/data", headers=auth)
    assert resp.headers["Content-Type"].startswith("application/json")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


# ---------------------------------------------------------------------------
# Token handling
# ---------------------------------------------------------------------------

def test_tampered_signature_is_rejected(client, token):
    header, payload, _sig = token.split(".")
    forged = f"{header}.{payload}.{'A' * len(_sig)}"
    resp = client.get("/api/data", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


def test_alg_none_token_is_rejected(client, token):
    _, payload, _ = token.split(".")
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    resp = client.get("/api/data", headers={"Authorization": f"Bearer {header}.{payload}."})
    assert resp.status_code == 401


def test_expired_token_is_rejected(client, app, token):
    claims = jwt.decode(token, app.config["JWT_SECRET"], algorithms=["HS256"],
                        audience=app.config["JWT_AUDIENCE"], issuer=app.config["JWT_ISSUER"])
    claims["exp"] = int(time.time()) - 60
    expired = jwt.encode(claims, app.config["JWT_SECRET"], algorithm="HS256")
    resp = client.get("/api/data", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert resp.get_json()["message"] == "Token has expired"


def test_logout_revokes_token(client, token):
    assert client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    resp = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.get_json()["message"] == "Token has been revoked"


def test_malformed_authorization_header(client):
    for value in ["", "Token abc", "Bearer", "Bearer a.b.c.d"]:
        resp = client.get("/api/data", headers={"Authorization": value})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Password storage and policy
# ---------------------------------------------------------------------------

def test_password_is_stored_as_bcrypt_hash(client, app):
    with app.app_context():
        from app.db import connect
        conn = connect(app.config["DATABASE_PATH"])
        stored = conn.execute("SELECT password_hash FROM users WHERE username='demo'").fetchone()[0]
        conn.close()
    assert stored.startswith("$2b$")
    assert "DemoPassw0rd!2024" not in stored


def test_registration_rejects_weak_password(client):
    resp = client.post("/auth/register", json={"username": "newbie", "password": "short", "display_name": "N"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "weak_password"


def test_registration_accepts_strong_password_and_login_works(client):
    resp = client.post(
        "/auth/register",
        json={"username": "alice", "password": "Str0ngPassphrase!", "display_name": "Alice"},
    )
    assert resp.status_code == 201
    login = client.post("/auth/login", json={"username": "alice", "password": "Str0ngPassphrase!"})
    assert login.status_code == 200


def test_duplicate_registration_conflicts(client):
    first = client.post("/auth/register",
                        json={"username": "bob", "password": "An0therStr0ngPass", "display_name": "Bob"})
    second = client.post("/auth/register",
                         json={"username": "bob", "password": "An0therStr0ngPass", "display_name": "Bob"})
    assert first.status_code == 201
    assert second.status_code == 409


# ---------------------------------------------------------------------------
# Brute-force protection
# ---------------------------------------------------------------------------

def test_login_is_rate_limited(client):
    codes = []
    for _ in range(7):
        codes.append(client.post("/auth/login", json={"username": "demo", "password": "nope"}).status_code)
    assert 429 in codes


# ---------------------------------------------------------------------------
# Hardening
# ---------------------------------------------------------------------------

def test_security_headers_present(client, auth):
    resp = client.get("/api/data", headers=auth)
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Cache-Control"] == "no-store"


def test_oversized_body_is_rejected(client, auth):
    big = "a" * (65 * 1024)
    resp = client.post("/api/posts", headers=auth, json={"title": "t", "body": big})
    assert resp.status_code in (400, 413)


def test_unknown_route_returns_json_404(client):
    resp = client.get("/nope")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "not_found"


def test_validation_errors_are_json_400(client, auth):
    # missing field
    missing = client.post("/api/posts", headers=auth, json={"body": "no title here"})
    assert missing.status_code == 400
    body = missing.get_json()
    assert body["error"] == "validation_error"
    assert body["field"] == "title"

    # oversized field
    long_title = client.post("/api/posts", headers=auth, json={"title": "x" * 200, "body": "b"})
    assert long_title.status_code == 400
    assert long_title.get_json()["field"] == "title"

    # wrong content type
    not_json = client.post("/api/posts", headers=auth, data="title=a", content_type="text/plain")
    assert not_json.status_code == 400
    assert not_json.get_json()["field"] == "body"
