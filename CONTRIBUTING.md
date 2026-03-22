# Contributing

## Development Setup

1. Install dependencies: `uv sync --all-extras --dev`
2. Make your changes.
3. Ensure pre-commit hooks pass: `prek run --all-files`
4. Ensure tests pass: `uv run -m pytest`
5. Submit a PR.

## Releasing a New Version

The version must be updated in **three** places (keep them in sync):

1. `pyproject.toml` — `version = "X.Y.Z"`
2. `wyoming_pocket_tts/__init__.py` — `__version__ = "X.Y.Z"`
3. `config.yaml` — `version: X.Y.Z` (Home Assistant add-on version)

Then update `CHANGELOG.md` with the changes.
