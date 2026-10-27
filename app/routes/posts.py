"""Data endpoints.

``GET /api/data``      -- protected list of posts (optional ``?q=`` search)
``POST /api/posts``    -- protected create
``GET /api/posts/<id>/preview`` -- HTML rendering that demonstrates output
                                   escaping (the XSS control) and a strict CSP
"""

from __future__ import annotations

from flask import Blueprint, Response, g, jsonify, request
from markupsafe import escape

from ..db import create_post, get_db, list_posts, get_post
from ..security import token_required
from ..validation import post_body, post_title, require_json, search_term

bp = Blueprint("data", __name__, url_prefix="/api")


def _serialise(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "author": row["author"],
        "created_at": row["created_at"],
    }


@bp.get("/data")
@token_required
def data():
    term = search_term(request.args.get("q"))
    rows = list_posts(get_db(), search=term)
    return jsonify(items=[_serialise(r) for r in rows], count=len(rows))


@bp.post("/posts")
@token_required
def create():
    payload = require_json(request)
    title = post_title(payload)
    body = post_body(payload)
    post_id = create_post(get_db(), g.current_user["id"], title, body)
    row = get_post(get_db(), post_id)
    return jsonify(_serialise(row)), 201


@bp.get("/posts/<int:post_id>")
@token_required
def show(post_id: int):
    row = get_post(get_db(), post_id)
    if row is None:
        return jsonify(error="not_found", status=404), 404
    return jsonify(_serialise(row))


@bp.get("/posts/<int:post_id>/preview")
@token_required
def preview(post_id: int):
    """Render a post as HTML.

    This is the *only* place where user data reaches an HTML document, and it
    is inserted exclusively through :func:`markupsafe.escape`.  Together with
    the CSP below, a stored ``<script>`` payload is rendered as literal text
    instead of being executed.
    """
    row = get_post(get_db(), post_id)
    if row is None:
        return jsonify(error="not_found", status=404), 404

    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{escape(row['title'])}</title></head><body>"
        f"<h1>{escape(row['title'])}</h1>"
        f"<p class='author'>by {escape(row['author'])}</p>"
        f"<article>{escape(row['body'])}</article>"
        "</body></html>"
    )
    resp = Response(html, mimetype="text/html")
    resp.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'"
    )
    return resp
