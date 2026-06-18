<p align="center">
  <img src="logo.png" alt="Wyoming Pocket TTS" width="400">
</p>

<p align="center">
  <strong>Fast, local text-to-speech with voice cloning for Home Assistant</strong>
</p>

<p align="center">
  <a href="https://github.com/araa47/wyoming_pocket_tts/actions/workflows/on-merge.yml"><img src="https://github.com/araa47/wyoming_pocket_tts/actions/workflows/on-merge.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/araa47/wyoming_pocket_tts/pkgs/container/wyoming_pocket_tts"><img src="https://img.shields.io/badge/ghcr.io-wyoming__pocket__tts-blue?logo=docker" alt="Docker"></a>
  <a href="https://github.com/araa47/wyoming_pocket_tts/blob/main/LICENSE"><img src="https://img.shields.io/github/license/araa47/wyoming_pocket_tts" alt="License"></a>
  <a href="https://github.com/araa47/wyoming_pocket_tts/releases"><img src="https://img.shields.io/github/v/release/araa47/wyoming_pocket_tts?include_prereleases&label=version" alt="Version"></a>
</p>

<p align="center">
  A <a href="https://github.com/rhasspy/wyoming">Wyoming protocol</a> server for <a href="https://kyutai.org/tts">Kyutai Pocket TTS</a> — ~10x realtime on CPU, no cloud, no GPU.
</p>

---

## Features

- **Fast** — ~10x realtime on CPU, no GPU required
- **Voice Cloning** — clone any voice from 15-30 seconds of audio
- **Multi-language** — English, French, German, Portuguese, Italian, and Spanish
- **Local** — 100% on-device, no cloud dependency
- **Wyoming Compatible** — plug into Home Assistant voice pipelines
- **Preset Voices** — expanded Pocket TTS preset catalog across supported languages

## Quick Start

### Docker (Recommended for standalone use)

```bash
docker run -d \
  --name pocket-tts \
  -p 10200:10200 \
  -v pocket-tts-voices:/share/tts-voices \
  ghcr.io/araa47/wyoming_pocket_tts:latest

# For voice cloning, add your HuggingFace token:
# -e HF_TOKEN=your_token_here
```

### Home Assistant Add-on

1. Go to **Settings > Add-ons > Add-on Store**
2. Click **...** > **Repositories** and add:
   ```
   https://github.com/araa47/wyoming_pocket_tts
   ```
3. Install **Wyoming Pocket TTS** and start it
4. The add-on auto-discovers in **Settings > Devices & Services**

> First startup downloads the TTS model (~500MB) and may take 3-5 minutes.

### Local Development

```bash
uv sync
uv run python -m wyoming_pocket_tts --voice alba --debug
```

## Requirements

| | |
|---|---|
| **Disk space** | ~1.5-2 GB (Docker image ~270 MB + model ~500 MB) |
| **Voice cloning** | Free [HuggingFace account](https://huggingface.co/join) with [accepted model terms](https://huggingface.co/kyutai/pocket-tts) |

> Built-in voices work without any HuggingFace setup. A token is only needed for voice cloning.

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `voice` | `alba` | Default voice |
| `language` | `en` | TTS language. Supported: `en`, `fr`, `de`, `pt`, `it`, `es`, plus `fr_24l`, `de_24l`, `pt_24l`, `italian_24l`, and `spanish_24l` |
| `voices_dir` | `/share/tts-voices` | Directory for custom voice samples |
| `preload_voices` | `''` | Voice name(s) to preload, e.g. `rocky` or `rocky,alba` (empty = only the default `voice`; `all` = every voice). Others load on first use |
| `debug` | `false` | Enable debug logging |
| `hf_token` | — | HuggingFace token (voice cloning only) |

## Languages

Set `language` in the add-on configuration or pass `--language` when running
locally. The default is `en`, so existing English and voice cloning setups keep
working without any configuration change.

Supported languages from Pocket TTS 2.1.0:

| Code | Language |
|------|----------|
| `en` / `english` | English |
| `fr` / `french` / `french_24l` | French |
| `de` / `german` / `german_24l` | German |
| `pt` / `portuguese` / `portuguese_24l` | Portuguese |
| `it` / `italian` / `italian_24l` | Italian |
| `es` / `spanish` / `spanish_24l` | Spanish |

Custom voice samples are loaded through the selected language model, matching
Pocket TTS's current API. Pocket TTS 2.1.0 ships cloning-capable weight paths for
all listed language configs. Those weights are gated by Kyutai's Hugging Face
model terms; if they cannot be downloaded, Pocket TTS falls back to
non-cloning weights, preset voices still work, and custom voices fall back to a
preset with a warning.

Rocky voice cloning was locally verified with Hugging Face access for English,
Spanish, French (`french_24l`), German, Portuguese, and Italian.

Default non-English preset voices are `estelle` for French, `juergen` for German,
`rafael` for Portuguese, `giovanni` for Italian, and `lola` for Spanish.

## Preset Voices

| Language | Voices |
|----------|--------|
| English | `alba`, `anna`, `azelma`, `bill_boerst`, `caro_davy`, `charles`, `cosette`, `eponine`, `eve`, `fantine`, `george`, `jane`, `jean`, `javert`, `marius`, `mary`, `michael`, `paul`, `peter_yearsley`, `stuart_bell`, `vera` |
| French | `estelle` |
| German | `juergen` |
| Portuguese | `rafael` |
| Italian | `giovanni` |
| Spanish | `lola` |

## Voice Cloning

> **Requires:** [HuggingFace token](https://huggingface.co/settings/tokens) with [accepted Pocket TTS model terms](https://huggingface.co/kyutai/pocket-tts).
>
> Custom voice samples are encoded by the selected `language` model. Keep
> `language: en` for the existing English cloning behavior. Other listed
> languages use the same Pocket TTS cloning API and have cloning-capable weight
> paths in Pocket TTS 2.1.0, but require Hugging Face access to Kyutai's gated
> cloning weights. Rocky cloning has been smoke-tested locally with HF access for
> English, Spanish, French, German, Portuguese, and Italian.

1. Record 15-30 seconds of clear speech (WAV, MP3, or OGG)
2. Copy to the voices directory:
   ```bash
   cp my_voice.wav /share/tts-voices/
   ```
3. Restart the add-on
4. Reload the Wyoming integration in Home Assistant:
   **Settings > Devices & Services > Wyoming Protocol > Pocket TTS > ... > Reload**
5. Use the voice by filename (without extension):
   ```yaml
   service: tts.speak
   data:
     entity_id: media_player.living_room
     message: "Hello from my cloned voice!"
     options:
       voice: my_voice
   ```

### Recording Tips

| Aspect | Recommendation |
|--------|----------------|
| **Length** | 15-30 seconds (minimum 5s) |
| **Quality** | 44.1 kHz, 16-bit, WAV preferred |
| **Content** | Natural conversation, not scripted |
| **Environment** | Quiet room, no echo |
| **Style** | Varied intonation (questions + statements) |

**Example prompt:**
> "Hey, so I was thinking about dinner tonight. Maybe pasta? Or we could order something. What do you think? Oh, and don't forget we have that thing tomorrow morning."

## API

The server speaks [Wyoming protocol](https://github.com/rhasspy/wyoming) on TCP port `10200`.

```bash
# Health check
echo '{"type":"describe"}' | nc localhost 10200

# Synthesize speech
echo '{"type":"synthesize","data":{"text":"Hello world","voice":{"name":"alba"}}}' | nc localhost 10200
```

## Troubleshooting

<details>
<summary><strong>"Gated model" error (voice cloning only)</strong></summary>

Built-in voices don't require HuggingFace access. For voice cloning:

1. Go to https://huggingface.co/kyutai/pocket-tts
2. Log in and accept the model terms
3. Get your token from https://huggingface.co/settings/tokens
4. Add it to the add-on config as `hf_token`

</details>

<details>
<summary><strong>Custom voice not appearing in Home Assistant</strong></summary>

Home Assistant caches the voice list. After adding a new voice:

1. Restart the Pocket TTS add-on
2. Go to **Settings > Devices & Services > Wyoming Protocol**
3. Click on your Pocket TTS device > **...** > **Reload**

</details>

<details>
<summary><strong>Voice not found</strong></summary>

- Check the filename matches (without extension)
- Ensure the file is in the `voices_dir` path
- Check add-on logs for loading errors

</details>

<details>
<summary><strong>Slow first request</strong></summary>

Each voice loads on first use (~2s). Set `preload_voices` to your voice name(s) (e.g. `rocky`) for instant first responses without loading every voice into RAM.

</details>

## License

MIT License — see [LICENSE](LICENSE).

Pocket TTS is licensed under CC-BY-4.0 with usage restrictions. See the [model card](https://huggingface.co/kyutai/pocket-tts) for terms.
