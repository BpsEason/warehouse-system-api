# Dockerfile — multi-stage build for FastAPI + Poetry applications

# ---------------------------
# Build stage
# ---------------------------
FROM python:3.13-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_HOME="/opt/poetry"

WORKDIR /app

# Install system dependencies needed to build wheels (psycopg2-binary, etc)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN python -m pip install --no-cache-dir "poetry>=1.2"

# Copy dependency declarations first for caching
COPY pyproject.toml poetry.lock* /app/

# Install project dependencies into system environment (no virtualenv inside container)
# --no-root prevents installing the project as editable; adjust if you want it installed
RUN poetry install --no-root --no-dev --no-interaction --no-ansi

# Copy application code
COPY . /app

# ---------------------------
# Runtime stage
# ---------------------------
FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Install minimal runtime dependencies for system libraries used by binary wheels if needed
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder: (Poetry installed into system site-packages in builder)
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY --from=builder /app /app

# Ensure non-root runtime
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONPATH=/app

EXPOSE 8000

# Use "app.main:app" as default; change if your FastAPI instance is located elsewhere
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]