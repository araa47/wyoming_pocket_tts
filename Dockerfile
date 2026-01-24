# Wyoming Pocket TTS Docker image
# Supports: amd64, aarch64
# Uses Debian for glibc compatibility (required for PyTorch wheels)

# For standalone use, can override with: ghcr.io/astral-sh/uv:python3.13-bookworm
ARG BUILD_FROM=ghcr.io/astral-sh/uv:python3.13-bookworm

FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install system dependencies for audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 \
    portaudio19-dev \
    netcat-openbsd \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Use system Python environment
ENV UV_SYSTEM_PYTHON=1
ENV UV_LINK_MODE=copy

# Copy project files and install dependencies (with cache mount for speed)
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r pyproject.toml

# Copy project source and install
COPY wyoming_pocket_tts/ wyoming_pocket_tts/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps .

# Copy run script
COPY run.sh /
RUN chmod +x /run.sh

# Create voices directory
RUN mkdir -p /share/tts-voices

# Expose Wyoming port
EXPOSE 10200

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD echo '{"type":"describe"}' | nc -w 5 localhost 10200 | grep -q "pocket-tts" || exit 1

# Run the server
CMD ["/run.sh"]
