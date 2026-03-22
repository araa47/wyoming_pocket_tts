# Agent Guidelines

- Use `uv` for all dependency management (`uv add`, `uv run`). Never use `requirements.txt`.
- Python 3.10+. Use modern type annotations where compatible with 3.10 (`list`, `dict`, not `List`, `Dict`).
- Before committing: run `prek run --all-files` and `uv run -m pytest`. All hooks and tests must pass.
- This is a Wyoming protocol TTS server for Home Assistant. Changes must maintain compatibility with the Wyoming protocol and Home Assistant add-on system.
- The project uses Kyutai's Pocket TTS model. Voice handling (preset + custom) is in `wyoming_pocket_tts/handler.py`.
