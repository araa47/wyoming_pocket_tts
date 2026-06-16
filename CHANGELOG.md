# Changelog

All notable changes to this project will be documented in this file.

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
