#!/usr/bin/env bash
# Run script for Wyoming Pocket TTS add-on
set -e

# Read options from Home Assistant add-on config
CONFIG_PATH=/data/options.json

# `voices` is a list; read it as a comma-separated string with jq. Older configs
# may still carry the legacy `voice`/`preload_voices` keys, so fall back to those
# when `voices` is empty (the server applies them only in that case).
read_voices() {
    jq -r 'if (.voices | type) == "array" then (.voices | join(","))
           elif (.voices | type) == "string" then .voices
           else "" end' "$CONFIG_PATH" 2>/dev/null
}
read_preload() {
    jq -r 'if (.preload_voices | type) == "array" then (.preload_voices | join(","))
           else (.preload_voices // "") end' "$CONFIG_PATH" 2>/dev/null
}

if command -v bashio &> /dev/null; then
    LANGUAGE=$(bashio::config 'language')
    VOICES_DIR=$(bashio::config 'voices_dir')
    DEBUG=$(bashio::config 'debug')
    HF_TOKEN=$(bashio::config 'hf_token')
    VOICES=$(read_voices)
    LEGACY_VOICE=$(jq -r '.voice // ""' "$CONFIG_PATH" 2>/dev/null)
    LEGACY_PRELOAD=$(read_preload)
else
    # Fallback to jq for standalone Docker
    if [ -f "$CONFIG_PATH" ]; then
        LANGUAGE=$(jq -r '.language // "en"' "$CONFIG_PATH")
        VOICES_DIR=$(jq -r '.voices_dir // "/share/tts-voices"' "$CONFIG_PATH")
        DEBUG=$(jq -r '.debug // false' "$CONFIG_PATH")
        HF_TOKEN=$(jq -r '.hf_token // ""' "$CONFIG_PATH")
        VOICES=$(read_voices)
        LEGACY_VOICE=$(jq -r '.voice // ""' "$CONFIG_PATH")
        LEGACY_PRELOAD=$(read_preload)
    else
        # Defaults for standalone usage
        LANGUAGE="${LANGUAGE:-en}"
        VOICES_DIR="${VOICES_DIR:-/share/tts-voices}"
        DEBUG="${DEBUG:-false}"
        HF_TOKEN="${HF_TOKEN:-}"
        VOICES="${VOICES:-alba}"
        LEGACY_VOICE="${LEGACY_VOICE:-}"
        LEGACY_PRELOAD="${LEGACY_PRELOAD:-}"
    fi
fi

# Export HuggingFace token if provided
if [ -n "$HF_TOKEN" ] && [ "$HF_TOKEN" != "null" ]; then
    export HF_TOKEN
    echo "HuggingFace token configured"
fi

# Create voices directory if it doesn't exist
mkdir -p "$VOICES_DIR"

# Build command arguments
ARGS=(
    --host "0.0.0.0"
    --port "10200"
    --language "$LANGUAGE"
    --voices-dir "$VOICES_DIR"
)

[ "$VOICES" = "null" ] && VOICES=""
ARGS+=(--voices "$VOICES")

# Legacy passthrough (used by the server only when --voices is empty).
[ "$LEGACY_VOICE" = "null" ] && LEGACY_VOICE=""
[ -n "$LEGACY_VOICE" ] && ARGS+=(--voice "$LEGACY_VOICE")
case "$LEGACY_PRELOAD" in
  true | True | TRUE) LEGACY_PRELOAD="all" ;;
  false | False | FALSE | null) LEGACY_PRELOAD="" ;;
esac
[ -n "$LEGACY_PRELOAD" ] && ARGS+=(--preload-voices "$LEGACY_PRELOAD")

if [ "$DEBUG" = "true" ]; then
    ARGS+=(--debug)
fi

echo "========================================"
echo "Wyoming Pocket TTS Server"
echo "========================================"
echo "Language: $LANGUAGE"
echo "Voices: ${VOICES:-<all built-in + custom (on demand)>}"
echo "Voices dir: $VOICES_DIR"
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
