# maayan — production image. The UI and the CLI (over SSH) share this same backend.
# Multi-arch: builds on Oracle's ARM Ampere (aarch64) and on x86 for local testing.
FROM python:3.12-slim

# uv: fast, reproducible installs straight from the committed uv.lock.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    HF_HOME=/app/.hf-cache \
    UI_HOST=0.0.0.0 \
    UI_PORT=8000

WORKDIR /app

# 1) Dependency layer (cached across code changes): needs the lock + project metadata.
#    pyproject reads README.md, so it must be present even for a metadata-only sync.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --extra ml --extra ui --no-install-project

# 2) Project layer: copy the package and install it into the venv.
COPY maayan ./maayan
RUN uv sync --frozen --no-dev --extra ml --extra ui

# Non-root user; writable dirs for the SQLite data + the bge-m3 model cache (both volumes).
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/.hf-cache /app/data \
    && chown -R app:app /app
USER app

EXPOSE 8000

# Liveness via the existing /healthz route. slim has no curl, so use python's urllib.
# Generous start-period: the first boot downloads bge-m3 (~2.3 GB) before uvicorn serves.
HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" \
        || exit 1

CMD ["uv", "run", "maayan", "ui"]
