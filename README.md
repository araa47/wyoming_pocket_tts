# Wyoming Pocket TTS

A [Wyoming protocol](https://github.com/rhasspy/wyoming) server for [Pocket TTS](https://kyutai.org/tts) - fast, local text-to-speech with voice cloning support.

## Features

- **Fast**: ~10x realtime on CPU (no GPU required)
- **Voice Cloning**: Clone any voice from 15-30 seconds of audio
- **Local**: 100% on-device, no cloud required
- **Wyoming Compatible**: Works with Home Assistant voice pipelines
- **8 Preset Voices**: alba, marius, javert, jean, fantine, cosette, eponine, azelma

## Requirements

- Home Assistant with Wyoming integration
- HuggingFace account (free) - [accept model terms](https://huggingface.co/kyutai/pocket-tts)

## Installation

### Option 1: Home Assistant Add-on Repository (Recommended)

1. **Add the repository to Home Assistant:**
   - Go to **Settings → Add-ons → Add-on Store**
   - Click the **⋮** menu (top right) → **Repositories**
   - Add: `https://github.com/araa47/wyoming-pocket-tts`
   - Click **Add** → **Close**

2. **Install the add-on:**
   - Refresh the page (or click **Check for updates**)
   - Find **"Wyoming Pocket TTS"** in the add-on store
   - Click **Install**

3. **Configure the add-on:**
   - Go to the **Configuration** tab
   - Set `hf_token`: Your HuggingFace token ([get one here](https://huggingface.co/settings/tokens))
   - Optionally change `voice` (default: "alba")
   - Click **Save**

4. **Start the add-on:**
   - Go to the **Info** tab
   - Click **Start**
   - Enable **Start on boot** if desired

5. **Connect to Home Assistant (Auto-Discovery):**
   
   The add-on should be **auto-discovered** by Home Assistant:
   - Go to **Settings → Devices & Services**
   - Look for **"Discovered"** section - you should see **Wyoming Pocket TTS**
   - Click **Configure** to add it
   
   **If not auto-discovered** (manual setup):
   - Click **Add Integration** → search for **Wyoming Protocol**
   - Enter:
     - Host: `core-wyoming-pocket-tts` (or the add-on hostname from the add-on info page)
     - Port: `10200`

6. **Set up Voice Assistant:**
   - Go to **Settings → Voice Assistants**
   - Edit your assistant (or create one)
   - Set **Text-to-speech** to **Wyoming Pocket TTS** (the device you just added)

### Option 2: Local Add-on (Manual)

If the repository isn't published yet, copy files manually:

1. Copy `wyoming_pocket_tts/` folder to `/config/addons_local/wyoming_pocket_tts/`
   ```bash
   # From your Home Assistant terminal/SSH
   mkdir -p /config/addons_local
   # Then copy/upload the wyoming_pocket_tts folder there
   ```

2. Go to **Settings → Add-ons → Add-on Store**

3. Click **⋮** menu → **Check for updates**

4. Find **"Wyoming Pocket TTS"** under **Local add-ons**

5. Follow steps 3-6 from Option 1 above

### Option 3: Standalone Docker

```bash
docker build -t wyoming-pocket-tts .

docker run -d \
  -p 10200:10200 \
  -v /path/to/voices:/share/tts-voices \
  -e HF_TOKEN=your_token_here \
  wyoming-pocket-tts
```

### Option 4: Local Development

```bash
cd wyoming_pocket_tts
uv sync
uv run python -m wyoming_pocket_tts --voice alba --debug
```

## Adding Custom Voices (Voice Cloning)

1. Record 15-30 seconds of clear speech (WAV, MP3, or OGG)

2. Copy to the voices directory:
   ```bash
   cp my_voice.wav /share/tts-voices/
   ```

3. Restart the add-on (or it will auto-detect on next request)

4. Use the voice by name (filename without extension):
   ```yaml
   service: tts.speak
   data:
     entity_id: media_player.living_room
     message: "Hello from my cloned voice!"
     options:
       voice: my_voice
   ```

### Voice Recording Tips

For best voice cloning results:

| Aspect | Recommendation |
|--------|----------------|
| **Length** | 15-30 seconds (minimum 5s) |
| **Quality** | 44.1kHz, 16-bit, WAV preferred |
| **Content** | Natural conversation, NOT scripted |
| **Environment** | Quiet room, no echo |
| **Style** | Varied intonation (questions + statements) |

**Good sample script:**
> "Hey, so I was thinking about dinner tonight. Maybe pasta? Or we could order something. What do you think? Oh, and don't forget we have that thing tomorrow morning."

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `voice` | `alba` | Default voice for TTS |
| `voices_dir` | `/share/tts-voices` | Directory for custom voice samples |
| `preload_voices` | `false` | Load all preset voices at startup |
| `debug` | `false` | Enable debug logging |
| `hf_token` | (required) | HuggingFace API token |

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

## API

The server implements the Wyoming protocol on TCP port 10200.

### Test with netcat

```bash
# Check if server is running
echo '{"type":"describe"}' | nc localhost 10200
```

### Synthesize speech

```bash
echo '{"type":"synthesize","data":{"text":"Hello world","voice":{"name":"alba"}}}' | nc localhost 10200
```

## Troubleshooting

### "Gated model" error
You need to accept the model terms:
1. Go to https://huggingface.co/kyutai/pocket-tts
2. Log in and accept the terms
3. Get your token from https://huggingface.co/settings/tokens
4. Add it to the add-on config

### Voice not found
- Check the filename matches (without extension)
- Ensure the file is in the `voices_dir` path
- Check add-on logs for loading errors

### Slow first request
The model loads on first request (~2s). Enable `preload_voices` for faster responses.

## License

MIT License - see LICENSE file.

Pocket TTS is licensed under CC-BY-4.0 with usage restrictions. See [model card](https://huggingface.co/kyutai/pocket-tts) for terms.
