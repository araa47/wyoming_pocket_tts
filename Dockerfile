# Wyoming-Kyutai TTS Docker image
# Supports: amd64, aarch64, armv7

ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install system dependencies and uv
RUN apk add --no-cache \
    build-base \
    git \
    libffi-dev \
    portaudio-dev \
    curl

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY wyoming_kyutai/ wyoming_kyutai/

# Install dependencies with uv
RUN uv pip install --system .

# Copy run script
COPY run.sh /
RUN chmod +x /run.sh

# Create voices directory
RUN mkdir -p /share/tts-voices

# Expose Wyoming port
EXPOSE 10200

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD echo '{"type":"describe"}' | nc -w 5 localhost 10200 | grep -q "kyutai" || exit 1

# Run the server
CMD ["/run.sh"]
