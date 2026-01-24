# Wyoming Pocket TTS

Fast, local text-to-speech with voice cloning for Home Assistant.

## About

This add-on runs [Pocket TTS](https://kyutai.org/tts), a lightweight TTS model that:

- Runs at ~10x realtime on CPU (no GPU needed)
- Supports voice cloning from short audio samples
- Works with Home Assistant's voice pipelines via Wyoming protocol

## Setup

### 1. Accept HuggingFace Terms

Before using this add-on, you must accept the model terms:

1. Go to [huggingface.co/kyutai/pocket-tts](https://huggingface.co/kyutai/pocket-tts)
2. Log in or create a free account
3. Click **"Agree and access repository"**

### 2. Get HuggingFace Token

1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Click **"New token"**
3. Name it (e.g., "home-assistant")
4. Select **"Read"** access
5. Copy the token (starts with `hf_`)

### 3. Configure Add-on

In the add-on Configuration tab:

| Option | Description |
|--------|-------------|
| `hf_token` | Your HuggingFace token (required) |
| `voice` | Default voice: alba, jean, fantine, etc. |
| `voices_dir` | Path for custom voice samples |
| `preload_voices` | Load all voices at startup (slower start, faster TTS) |
| `debug` | Enable verbose logging |

### 4. Start Add-on & Connect to Home Assistant

1. **Start the add-on** from the Info tab

2. **Wait for auto-discovery** (recommended):
   - Go to **Settings → Devices & Services**
   - Look in the **"Discovered"** section for **Wyoming Pocket TTS**
   - Click **Configure** to add it

3. **Manual setup** (if not auto-discovered):
   - Go to **Settings → Devices & Services**
   - Click **Add Integration** → **Wyoming Protocol**
   - Host: Find the hostname in the add-on's **Info** tab (looks like `xxxxxxxx-wyoming-pocket-tts`)
   - Port: `10200`
   
   **Note**: First startup may take 3-5 minutes to download the TTS model (~500MB).

4. **Set up Voice Assistant**:
   - Go to **Settings → Voice Assistants**
   - Edit or create an assistant
   - Set **Text-to-speech** to the Wyoming device you just added

## Adding Custom Voices

Clone any voice from a short audio sample:

1. Record 15-30 seconds of clear speech (WAV, MP3, or OGG)
2. Upload to `/share/tts-voices/` via Samba/SSH
3. Name the file (e.g., `my_voice.wav`)
4. Restart the add-on to load the new voice
5. **Reload the Wyoming integration** to update the voice list:
   - Go to **Settings → Devices & Services**
   - Click on your **Pocket TTS** device under Wyoming Protocol
   - Click **⋮** menu → **Reload**
6. Use `my_voice` as the voice name in automations

> **Important**: Home Assistant caches the voice list. Without step 5, your new voice won't appear in the voice dropdown when configuring assistants.

### Recording Tips

- **Length**: 15-30 seconds works best
- **Quality**: 44.1kHz, quiet environment
- **Style**: Natural conversation, varied intonation
- **Content**: Mix of questions and statements

## Usage in Automations

```yaml
service: tts.speak
target:
  entity_id: media_player.living_room
data:
  message: "Dinner is ready!"
  options:
    voice: alba  # or your custom voice name
```

## Preset Voices

| Voice | Description |
|-------|-------------|
| alba | Female, neutral American |
| marius | Male, casual |
| javert | Male, authoritative |
| jean | Male, warm |
| fantine | Female, expressive |
| cosette | Female, gentle |
| eponine | Female, British |
| azelma | Female, youthful |

## Troubleshooting

### "Model not found" or "401 Unauthorized"

- Ensure you've accepted terms at huggingface.co/kyutai/pocket-tts
- Check your HF token is correct and has Read access

### Slow first response

The model loads on first request (~2-3 seconds). Enable `preload_voices` for instant responses.

### Custom voice not appearing in dropdown

Home Assistant caches the voice list. After adding a new voice:

1. Restart the Pocket TTS add-on
2. Go to **Settings → Devices & Services → Wyoming Protocol**
3. Click on your Pocket TTS device → **⋮** menu → **Reload**

### Custom voice not found

- Check filename matches exactly (case-sensitive, without extension)
- Verify file is in `/share/tts-voices/`
- Check add-on logs for loading errors

## Support

- GitHub Issues: [github.com/araa47/wyoming_pocket_tts/issues](https://github.com/araa47/wyoming_pocket_tts/issues)
- Pocket TTS Docs: [kyutai.org/tts](https://kyutai.org/tts)
