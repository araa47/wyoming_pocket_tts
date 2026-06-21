# Changelog

All notable changes to this project will be documented in this file.

## [1.4.1] - 2026-06-21

### Fixed
- Add-on disappearing from the Home Assistant Add-on Store with the error
  "App has been removed from the repository it was installed from." The v1.4.0
  `config.yaml` introduced an unsupported `options_description` key and used the
  invalid `select(...)` schema type, both of which fail Supervisor validation
  and cause the add-on to be dropped from the repository.
  - Removed the unsupported `options_description` block (option docs already
    live in `DOCS.md`).
  - Changed the `voice` and `language` dropdowns from `select(...)` to the
    correct add-on schema type `list(...)`.

## [1.4.0] - 2026-06-18

### Changed
- Home Assistant add-on `language` field is now a dropdown select with all
  supported languages.
- Home Assistant add-on `voice` field is now a dropdown select with built-in
  voice options.
- Home Assistant add-on `preload_voices` is now a list input.
- Improved README with a clearer quick start, voice cloning guide, language
  table, and built-in voice reference.

## [1.3.0] - 2026-06-18

### Added
- Multi-language support via the `--language` flag and Home Assistant add-on
  `language` option. The default remains `en` for fully backward-compatible
  English behavior.
- Supported languages from Pocket TTS 2.1.0: English (`en`/`english`), French
  (`fr`/`french`, `french_24l`), German (`de`/`german`, `german_24l`),
  Portuguese (`pt`/`portuguese`, `portuguese_24l`), Italian (`it`/`italian`,
  `italian_24l`), and Spanish (`es`/`spanish`, `spanish_24l`).
- Expanded preset voice catalog from Pocket TTS 2.1.0.

### Notes
- English voice cloning behavior is unchanged and remains fully supported.
- Custom voice samples are loaded through the selected language model, matching
  Pocket TTS's current API. Pocket TTS 2.1.0 includes cloning-capable weight
  paths for every listed language config; if gated cloning weights cannot be
  downloaded, preset voices continue to work and custom voices fall back to a
  preset with a warning.
- Rocky cloning was smoke-tested locally with HF access for English, Spanish,
  French, German, Portuguese, and Italian.

## [1.2.0] - 2026-06-18

### Changed
- **Audio is now streamed as it is generated** instead of being buffered until the
  whole clip is synthesized. The handler uses Pocket TTS's `generate_audio_stream`
  and forwards each `AudioChunk` as it is decoded, so Home Assistant receives the
  first audio after ~one chunk rather than after the full utterance. On CPU, Pocket
  TTS runs at roughly real time, so buffering previously delayed all audio by the
  clip's full duration and could trip Home Assistant's TTS timeout on long replies
  (seen as a dropped connection mid-response and the voice satellite's LED/phase
  state desyncing from the actual speech). Streaming fixes that and lets satellites
  start playback — and show the "speaking" state — promptly. Generation is
  serialized with a lock since Pocket TTS's streaming generator is not thread-safe
  on a shared model.

### Removed
- **`normalize_volume` and `normalize_target_db` options.** Peak normalization
  needed the whole clip up front (its global peak), which is incompatible with
  streaming, and is no longer used. Clone from a clear, loud section of the source
  recording for good output level. Remove these keys from your add-on config if
  present.

## [1.1.0] - 2026-06-16

### Changed
- **`preload_voices` is now a list of voice names instead of a boolean.** Set it to
  the voice(s) you actually use (e.g. `rocky`, or `rocky,alba`) to preload only those.
  Empty (the new default) preloads just the configured `voice`; `all` preloads every
  preset and custom voice (the old `true` behaviour). This sharply cuts memory: preloading
  all voices held every voice state in RAM (~1.9 GB observed) and could OOM-kill the
  add-on on memory-constrained hosts, which surfaced as intermittent TTS failures.

### Added
- On-demand voice loading now covers **custom** voices, not just presets — so any voice
  that is not preloaded still works on first use (loaded lazily from the voices directory).

### Migration
- The `preload_voices` option type changed from boolean to string. If yours was `true`,
  set it to `all` (same behaviour) or, better, to your voice name(s) like `rocky`. `false`
  or empty now preloads only the default voice. Legacy `true`/`false` values are mapped
  automatically by the run script; update the option in the UI if Home Assistant flags it.

## [1.0.6] - 2026-06-04

### Added
- **`normalize_volume` option** to peak-normalize generated speech. Pocket TTS
  output level follows the loudness of the voice prompt, so quiet cloning
  samples produce quiet speech that is weak on a speaker even at full device
  volume. Normalization scales each clip so its loudest sample reaches
  `normalize_target_db` (default `-1` dBFS) — a lossless, non-clipping gain.
- **`normalize_target_db` option** to set the normalization ceiling.

## [1.0.4] - 2026-01-29

### Changed
- **Docker image reduced by 56%** (613MB → 269MB compressed) using multi-stage builds and UV best practices
- Switched to `bookworm-slim` base images for smaller footprint
- Added bytecode compilation (`UV_COMPILE_BYTECODE=1`) for faster container startup
- Removed unnecessary files from final image (test dirs, header files, unused Caffe2)
- UV is no longer included in the final runtime image (only used during build)

### Technical Details
- Builder stage: `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`
- Runtime stage: `python:3.13-slim-bookworm`
- Uncompressed size reduced from 2.63GB to 1.25GB

## [1.0.3] - 2026-01-29

### Changed
- **Reduced disk usage from ~15GB to ~2.5GB** by using CPU-only PyTorch instead of the full CUDA-enabled version (#3, #4)
- Simplified preset voice loading to use voice names directly instead of HuggingFace URLs

### Added
- Disk space requirement (~2-3GB) documented in README

## [1.0.2] - 2026-01-26

### Fixed
- Added `soundfile` dependency for non-WAV voice cloning support (#2)

## [1.0.1] - 2026-01-25

### Fixed
- Fixed on-demand voice loading for preset voices

## [1.0.0] - 2026-01-25

### Added
- Initial release
- Wyoming protocol server for Pocket TTS
- Support for 8 preset voices (alba, marius, javert, jean, fantine, cosette, eponine, azelma)
- Voice cloning from custom audio files (requires HuggingFace token)
- Home Assistant add-on support with auto-discovery
- Docker support for standalone deployment
