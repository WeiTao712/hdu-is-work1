FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

WORKDIR /app

# Dependencies first: this layer is cached between builds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt waitress==3.0.0

COPY app ./app
COPY run.py .

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /var/lib/work1 \
    && chown -R appuser:appuser /app /var/lib/work1
USER appuser

ENV DATABASE_PATH=/var/lib/work1/app.db

EXPOSE 8000
# waitress is a production WSGI server; the Flask dev server is never used.
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8000", "run:app"]
