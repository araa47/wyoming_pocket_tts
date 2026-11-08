"""Tests for the Supervisor discovery payload sent by ``run.sh``.

Issue #38: Home Assistant stores the discovered host in the Wyoming config
entry and never updates it on rediscovery. 1.4.3-1.4.8 advertised the add-on's
container IPv4 address, which changes whenever Docker re-assigns hassio IPs
(add-on restart, host reboot), leaving the integration permanently "Unable to
connect" until it was deleted and re-added. Discovery must advertise the stable
add-on hostname instead.

The test extracts the real ``send_discovery`` function from ``run.sh`` and runs
it with stubbed ``hostname``/``nc``/``curl``/``sleep`` on ``PATH``.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RUN_SH = Path(__file__).resolve().parent.parent / "run.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash is required to exercise run.sh"
)


def _send_discovery_source() -> str:
    match = re.search(
        r"^send_discovery\(\) \{\n.*?^\}\n", RUN_SH.read_text(), re.S | re.M
    )
    assert match, "send_discovery() not found in run.sh"
    return match.group(0)


def _stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(0o755)


@pytest.fixture
def stub_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    payload_file = tmp_path / "payload.json"
    # Docker hostname as the Supervisor sets it ({REPO}_{SLUG}); `hostname -i`
    # returns a container IP that changes across restarts.
    _stub(
        bin_dir,
        "hostname",
        'if [ "$1" = "-i" ]; then echo "172.30.33.7 fd0c:ac1e:2100::e"; '
        "else echo 6273f1c6_wyoming_pocket_tts; fi\n",
    )
    _stub(
        bin_dir, "getent", "echo '172.30.33.7     STREAM 6273f1c6-wyoming-pocket-tts'\n"
    )
    _stub(
        bin_dir,
        "nc",
        'cat >/dev/null; echo \'{"type":"info","program":"pocket-tts"}\'\n',
    )
    _stub(bin_dir, "sleep", "exit 0\n")
    _stub(
        bin_dir,
        "curl",
        'while [ $# -gt 0 ]; do if [ "$1" = "-d" ]; then shift; '
        f'printf "%s" "$1" > "{payload_file}"; fi; shift; done\n'
        'echo \'{"result": "ok", "data": {}}\'\n',
    )
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "SUPERVISOR_TOKEN": "test-token",
    }
    return env, payload_file


def _run_discovery(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    script = _send_discovery_source() + "send_discovery\n"
    return subprocess.run(
        ["bash", "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_discovery_advertises_stable_hostname(stub_env):
    env, payload_file = stub_env
    result = _run_discovery(env)
    assert result.returncode == 0, result.stdout + result.stderr

    payload = json.loads(payload_file.read_text())
    assert payload["service"] == "wyoming"
    # Hyphenated hostname, never the (unstable) container IP.
    assert payload["config"]["uri"] == "tcp://6273f1c6-wyoming-pocket-tts:10200"


def test_discovery_skipped_outside_supervisor(stub_env):
    env, payload_file = stub_env
    env.pop("SUPERVISOR_TOKEN")
    result = _run_discovery(env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "skipping discovery" in result.stdout
    assert not payload_file.exists()
