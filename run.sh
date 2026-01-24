#!/usr/bin/env bash
# Run script for Wyoming Pocket TTS add-on
set -e

# Read options from Home Assistant add-on config
CONFIG_PATH=/data/options.json

# Parse config with bashio if available, otherwise use jq
if command -v bashio &> /dev/null; then
    VOICE=$(bashio::config 'voice')
    VOICES_DIR=$(bashio::config 'voices_dir')
    PRELOAD_VOICES=$(bashio::config 'preload_voices')
    DEBUG=$(bashio::config 'debug')
    HF_TOKEN=$(bashio::config 'hf_token')
else
    # Fallback to jq for standalone Docker
    if [ -f "$CONFIG_PATH" ]; then
        VOICE=$(jq -r '.voice // "alba"' "$CONFIG_PATH")
        VOICES_DIR=$(jq -r '.voices_dir // "/share/tts-voices"' "$CONFIG_PATH")
        PRELOAD_VOICES=$(jq -r '.preload_voices // false' "$CONFIG_PATH")
        DEBUG=$(jq -r '.debug // false' "$CONFIG_PATH")
        HF_TOKEN=$(jq -r '.hf_token // ""' "$CONFIG_PATH")
    else
        # Defaults for standalone usage
        VOICE="${VOICE:-alba}"
        VOICES_DIR="${VOICES_DIR:-/share/tts-voices}"
        PRELOAD_VOICES="${PRELOAD_VOICES:-false}"
        DEBUG="${DEBUG:-false}"
        HF_TOKEN="${HF_TOKEN:-}"
    fi
fi

# Export HuggingFace token if provided
if [ -n "$HF_TOKEN" ]; then
    export HF_TOKEN
    echo "HuggingFace token configured"
fi

# Create voices directory if it doesn't exist
mkdir -p "$VOICES_DIR"

# Build command arguments
ARGS=(
    --host "0.0.0.0"
    --port "10200"
    --voice "$VOICE"
    --voices-dir "$VOICES_DIR"
)

if [ "$PRELOAD_VOICES" = "true" ]; then
    ARGS+=(--preload-voices)
fi

if [ "$DEBUG" = "true" ]; then
    ARGS+=(--debug)
fi

echo "========================================"
echo "Wyoming Pocket TTS Server"
echo "========================================"
echo "Voice: $VOICE"
echo "Voices dir: $VOICES_DIR"
echo "Preload voices: $PRELOAD_VOICES"
echo "Debug: $DEBUG"
echo "========================================"

# Run the server (packages installed to system Python)
exec python3 -m wyoming_pocket_tts "${ARGS[@]}"
