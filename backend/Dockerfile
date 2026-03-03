FROM python:3.12-slim AS base

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
# All deps ship manylinux wheels — no build-essential/libpq-dev needed
COPY pyproject.toml uv.lock ./
# Install all deps including dev extras (pytest, ruff) so tests can run inside container
RUN uv sync --all-extras --no-install-project

# Copy application code
COPY alembic.ini ./
COPY alembic/ alembic/
COPY app/ app/
COPY tests/ tests/

# Expose port
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run with uvicorn
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
