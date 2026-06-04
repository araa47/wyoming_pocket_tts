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
    NORMALIZE_VOLUME=$(bashio::config 'normalize_volume')
    NORMALIZE_TARGET_DB=$(bashio::config 'normalize_target_db')
    DEBUG=$(bashio::config 'debug')
    HF_TOKEN=$(bashio::config 'hf_token')
else
    # Fallback to jq for standalone Docker
    if [ -f "$CONFIG_PATH" ]; then
        VOICE=$(jq -r '.voice // "alba"' "$CONFIG_PATH")
        VOICES_DIR=$(jq -r '.voices_dir // "/share/tts-voices"' "$CONFIG_PATH")
        PRELOAD_VOICES=$(jq -r '.preload_voices // false' "$CONFIG_PATH")
        NORMALIZE_VOLUME=$(jq -r '.normalize_volume // false' "$CONFIG_PATH")
        NORMALIZE_TARGET_DB=$(jq -r '.normalize_target_db // -1' "$CONFIG_PATH")
        DEBUG=$(jq -r '.debug // false' "$CONFIG_PATH")
        HF_TOKEN=$(jq -r '.hf_token // ""' "$CONFIG_PATH")
    else
        # Defaults for standalone usage
        VOICE="${VOICE:-alba}"
        VOICES_DIR="${VOICES_DIR:-/share/tts-voices}"
        PRELOAD_VOICES="${PRELOAD_VOICES:-false}"
        NORMALIZE_VOLUME="${NORMALIZE_VOLUME:-false}"
        NORMALIZE_TARGET_DB="${NORMALIZE_TARGET_DB:--1}"
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
    --normalize-target-db "$NORMALIZE_TARGET_DB"
)

if [ "$PRELOAD_VOICES" = "true" ]; then
    ARGS+=(--preload-voices)
fi

if [ "$NORMALIZE_VOLUME" = "true" ]; then
    ARGS+=(--normalize-volume)
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
echo "Normalize volume: $NORMALIZE_VOLUME (target ${NORMALIZE_TARGET_DB} dBFS)"
echo "Debug: $DEBUG"
echo "========================================"

# Function to send discovery info to Home Assistant
send_discovery() {
    # Wait for the server to be ready (up to 5 minutes for first model download)
    local max_wait=300
    local waited=0
    echo "Waiting for Wyoming server to be ready for discovery..."

    while [ $waited -lt $max_wait ]; do
        if echo '{"type":"describe"}' | nc -w 2 localhost 10200 2>/dev/null | grep -q "pocket-tts"; then
            echo "Server is ready after ${waited}s"
            break
        fi
        sleep 2
        waited=$((waited + 2))
    done

    if [ $waited -ge $max_wait ]; then
        echo "Warning: Timed out waiting for server to start for discovery"
        return 1
    fi

    # Small delay to ensure server is fully ready
    sleep 1

    # Check if running in Home Assistant (supervisor API available)
    if [ -n "$SUPERVISOR_TOKEN" ]; then
        local hostname
        # Get hostname and convert underscores to hyphens for valid DNS name
        # Home Assistant uses {REPO}_{SLUG} but DNS requires hyphens
        hostname=$(hostname | tr '_' '-')
        echo "Sending discovery for host: ${hostname}:10200"

        # Retry discovery up to 3 times
        local retry=0
        local max_retries=3
        while [ $retry -lt $max_retries ]; do
            local response
            response=$(curl -s -X POST \
                -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
                -H "Content-Type: application/json" \
                -d "{\"service\": \"wyoming\", \"config\": {\"uri\": \"tcp://${hostname}:10200\"}}" \
                "http://supervisor/discovery" 2>&1)

            if echo "$response" | grep -q '"result".*"ok"'; then
                echo "Successfully sent discovery information to Home Assistant"
                return 0
            else
                echo "Discovery attempt $((retry + 1)) response: $response"
                retry=$((retry + 1))
                sleep 2
            fi
        done
        echo "Warning: Failed to send discovery after ${max_retries} attempts"
    else
        echo "Not running in Home Assistant (no SUPERVISOR_TOKEN) - skipping discovery"
    fi
}

# Start discovery in background (will wait for server to be ready)
send_discovery &

# Run the server (packages installed to system Python)
exec python3 -m wyoming_pocket_tts "${ARGS[@]}"
