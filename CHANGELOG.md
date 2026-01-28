# Changelog

All notable changes to this project will be documented in this file.

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
