# Wyoming Pocket TTS

Fast, local text-to-speech with voice cloning for Home Assistant.

## About

This add-on runs [Pocket TTS](https://kyutai.org/tts), a lightweight TTS model that:

- Runs at ~10x realtime on CPU (no GPU needed)
- Supports voice cloning from short audio samples
- Works with Home Assistant's voice pipelines via Wyoming protocol

## Setup

### 1. Configure TTS

Built-in voices work without a Hugging Face account or token.

In the add-on Configuration tab:

| Option | Description |
|--------|-------------|
| `language` | TTS language/model to load. Default `en`. Supported: `en`, `fr`, `de`, `pt`, `it`, `es`, plus the 24-layer variants `fr_24l`, `de_24l`, `pt_24l`, `it_24l`, and `es_24l` |
| `voices` | The voices to load. Type one name per entry. Each listed voice is **preloaded** (fast first response) and is the **only** set advertised to Home Assistant. Use a preset name (see list below) or a custom sample's filename **without extension** (e.g. `rocky`). Leave empty to advertise every built-in + custom voice (loaded on demand) |
| `voices_dir` | Folder for custom voice samples. Keep `/share/tts-voices` for Home Assistant add-on installs. Put `<name>.ogg`, `.wav`, `.mp3`, `.flac`, or `.m4a` files here and reference them as `<name>` |
| `hf_token` | Hugging Face read token. Required only for custom (cloned) voices |
| `debug` | Enable verbose logging |

**Built-in preset names** — English: `alba`, `anna`, `azelma`, `bill_boerst`,
`caro_davy`, `charles`, `cosette`, `eponine`, `eve`, `fantine`, `george`, `jane`,
`jean`, `javert`, `marius`, `mary`, `michael`, `paul`, `peter_yearsley`,
`stuart_bell`, `vera`. Other languages: `estelle` (fr), `juergen` (de),
`rafael` (pt), `giovanni` (it), `lola` (es).

**Built-in only** — set `language` and put one or more preset names in `voices`
(e.g. `alba`). Done.

**Custom (cloned) voice** — e.g. to use only your `rocky.ogg`:

1. Put `rocky.ogg` in `/share/tts-voices` (see *Adding Custom Voices* below)
2. Set `hf_token` (cloning requires it — see *Optional: Enable Voice Cloning*)
3. Set `voices` to a single entry: `rocky` (filename without extension)
4. Pick the matching `language`
5. Start/restart the add-on, then reload the Wyoming integration

Now only `rocky` is preloaded and offered to Home Assistant.

> **Language note:** English (`en`) keeps the existing behavior.
> Custom voice samples are loaded through the selected Pocket TTS language model.
> Pocket TTS 2.1.0 includes cloning-capable weight paths for every listed language
> config. If those gated weights are unavailable, preset voices continue to work
> and custom voices fall back to a preset with a warning.
> Rocky cloning has been smoke-tested locally with HF access for English,
> Spanish, French, German, Portuguese, and Italian.

> **Tip:** Pocket TTS output volume follows the loudness of your voice prompt — a
> quiet cloning sample yields quiet speech that sounds weak on a speaker even at
> full device volume. For best results, clone from a clear, loud section of your
> source recording.

### 2. Start Add-on & Connect to Home Assistant

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

### 3. Optional: Enable Voice Cloning

Voice cloning requires Hugging Face access to Kyutai's gated cloning weights.

1. Go to [huggingface.co/kyutai/pocket-tts](https://huggingface.co/kyutai/pocket-tts)
2. Log in or create a free account
3. Click **"Agree and access repository"**
4. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
5. Create a **Read** token
6. Paste the token into `hf_token` in the add-on Configuration tab
7. Restart the add-on

## Adding Custom Voices

Clone any voice from a short audio sample:

1. Record 5-30 seconds of clear speech; 15-30 seconds works best
2. Upload to `/share/tts-voices/` via Samba/SSH
3. Name the file (e.g., `my_voice.wav`)
4. Add `my_voice` to the `voices` option (and set `hf_token`)
5. Restart the add-on to load the new voice
6. **Reload the Wyoming integration** to update the voice list:
   - Go to **Settings → Devices & Services**
   - Click on your **Pocket TTS** device under Wyoming Protocol
   - Click **⋮** menu → **Reload**
7. Use `my_voice` as the voice name in automations

> **Important**: Home Assistant caches the voice list. Without step 6, your new
> voice won't appear in the voice dropdown when configuring assistants.

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

Voices listed in `voices` are preloaded, so the first response is instant. If you
leave `voices` empty, voices load on first use (~2-3 seconds) instead — add the
ones you use to `voices` to preload them.

### Voice dropdown is empty / TTS entity unavailable

Home Assistant must be able to reach the add-on over the Wyoming protocol. If the
Wyoming integration shows "unable to connect" (entity `unavailable`), reload it:
**Settings → Devices & Services → Wyoming Protocol → your Pocket TTS device →
⋮ → Reload**. (Older versions bound IPv4 only and could be unreachable on
dual-stack networks; this is fixed in 1.4.2+.)

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
