FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies if needed (e.g. for C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

FROM python:3.12-slim

# Create a non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

# Copy the pre-built wheels from the builder
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Install the wheels
RUN pip install --no-cache /wheels/*

# Copy application source
COPY --chown=appuser:appgroup . /app

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Deterministic production startup command via gunicorn with uvicorn workers
CMD ["gunicorn", "app.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
