"""Development entry point: ``python run.py``.

The Flask development server is used *only* for local testing.  In any real
deployment the WSGI app is served by gunicorn/waitress behind a TLS proxy.
"""

from __future__ import annotations

import os

from app import create_app
from app.config import Config

app = create_app(Config)

if __name__ == "__main__":
    Config.validate()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=False)
