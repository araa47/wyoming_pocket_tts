# Wyoming Pocket TTS Docker image - Optimized
# Uses multi-stage build for minimal final image size
# Supports: amd64, aarch64

# ============================================
# BUILDER STAGE - Install dependencies with uv
# ============================================
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install build dependencies for audio libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libportaudio2 \
    portaudio19-dev \
    libsndfile1 \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# UV settings for optimized builds
ENV UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install CPU-only PyTorch first (avoids 15GB CUDA deps)
# Then install project dependencies
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install -r pyproject.toml

# Copy project source and install (non-editable for smaller image)
COPY wyoming_pocket_tts/ wyoming_pocket_tts/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps .

# Clean up unnecessary files from site-packages to reduce image size
RUN find /usr/local/lib/python3.13/site-packages -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.13/site-packages -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.13/site-packages -type d -name "__pycache__" -name "*.py" -delete 2>/dev/null || true && \
    find /usr/local/lib/python3.13/site-packages -type f -name "*.pyi" -delete 2>/dev/null || true && \
    find /usr/local/lib/python3.13/site-packages -type f -name "*.pyx" -delete 2>/dev/null || true && \
    find /usr/local/lib/python3.13/site-packages -type f -name "*.c" -delete 2>/dev/null || true && \
    find /usr/local/lib/python3.13/site-packages -type f -name "*.h" -delete 2>/dev/null || true && \
    rm -rf /usr/local/lib/python3.13/site-packages/torch/include 2>/dev/null || true && \
    rm -rf /usr/local/lib/python3.13/site-packages/torch/share 2>/dev/null || true && \
    rm -rf /usr/local/lib/python3.13/site-packages/caffe2 2>/dev/null || true

# ============================================
# RUNTIME STAGE - Minimal final image
# ============================================
FROM python:3.13-slim-bookworm

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install only runtime dependencies (no build tools, no uv)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 \
    libsndfile1 \
    netcat-openbsd \
    jq \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Copy Python packages from builder (system site-packages)
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/wyoming-pocket-tts /usr/local/bin/

WORKDIR /app

# Copy run script
COPY run.sh /run.sh
RUN chmod +x /run.sh

# Create voices directory
RUN mkdir -p /share/tts-voices

# Expose Wyoming port
EXPOSE 10200

# Health check (start-period=300s allows time for model download on first run)
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD echo '{"type":"describe"}' | nc -w 5 localhost 10200 | grep -q "pocket-tts" || exit 1

# Run the server
CMD ["/run.sh"]
