"""Tests for config.yaml add-on schema.

Issue #29: the bogus ``environment:`` block (which templated ``HF_TOKEN`` via
``{{ .hf_token }}``) must stay removed -- the Supervisor does not perform
template substitution in add-on ``environment`` values, so the block only ever
exported the literal template string. The ``hf_token`` option/schema entry is
the supported path (read by ``run.sh``) and must remain.
"""

from pathlib import Path

CONFIG_YAML = Path(__file__).resolve().parent.parent / "config.yaml"


def test_config_has_no_environment_block():
    """The bogus ``environment:`` block must be absent (see issue #29)."""
    text = CONFIG_YAML.read_text()
    assert "environment:" not in text
    # The orphaned comment that introduced the block must also be gone.
    assert "# Environment" not in text


def test_hf_token_option_is_preserved():
    """The ``hf_token`` option must still be exposed in the add-on UI."""
    text = CONFIG_YAML.read_text()
    assert "hf_token:" in text


def test_hf_token_schema_entry_is_preserved():
    """The ``hf_token`` schema entry (``password?``) must remain intact."""
    text = CONFIG_YAML.read_text()
    assert "hf_token: password?" in text
