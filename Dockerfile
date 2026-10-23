# ==============================================================================
# Multi-stage Dockerfile: Compiles Rust domain engine (microbond_core) via Maturin,
# then produces a secure, minimal Python runtime image for Render and Cloud Run.
# ==============================================================================

# ── Stage 1: Build Rust Domain Extension Wheel ────────────────────────────────
FROM rust:1.80-slim AS rust-builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/maturin-venv && \
    /opt/maturin-venv/bin/pip install --no-cache-dir maturin

COPY microbond_core ./microbond_core

RUN cd microbond_core && \
    /opt/maturin-venv/bin/maturin build --release --out /wheels

# ── Stage 2: Final Production Runtime ─────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# 1. Install compiled Rust wheel from builder stage
COPY --from=rust-builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

# 2. Install application Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 3. Copy application codebase (respecting .dockerignore)
COPY . .

# 4. Run as non-privileged security user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000 8080 10000

# Universal runtime command: automatically runs pending database migrations,
# then binds uvicorn to $PORT provided by Render (10000), Cloud Run (8080), or Local (8000)
CMD sh -c "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"
