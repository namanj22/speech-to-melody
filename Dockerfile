# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed to compile native extensions (librosa → llvmlite → numba)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libsndfile1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Speech-to-Melody Converter"
LABEL org.opencontainers.image.description="Extract pitch from speech, map to musical scales, synthesize melody"

# Runtime system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
        libsndfile1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy project source
COPY core/           ./core/
COPY app.py          .
COPY wsgi.py         .
COPY requirements.txt .

# Create writable storage dirs (will be used for uploads & generated files)
ENV STORAGE_DIR=/tmp/speech_melody
ENV MPLBACKEND=Agg
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Port — Railway/Render inject $PORT at runtime; default 8000
ENV PORT=8000
EXPOSE 8000

# Health-check endpoint (Flask serves / so this just hits the index)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/')" || exit 1

# gunicorn:
#   --workers 2        2 worker processes (CPU-bound pitch extraction is heavy)
#   --threads 4        4 threads per worker for concurrent I/O
#   --timeout 120      allow up to 2 min for large files
#   --worker-class gthread
CMD gunicorn wsgi:application \
        --workers 2 \
        --worker-class gthread \
        --threads 4 \
        --timeout 120 \
        --bind "0.0.0.0:${PORT}" \
        --log-level info \
        --access-logfile - \
        --error-logfile -
