"""Network-free CLI surface contracts."""

from __future__ import annotations

import subprocess
import sys


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_tech_guardian", *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )


def test_cli_help_exits_zero_without_running_monitor():
    completed = invoke("--help")
    assert completed.returncode == 0
    assert "Agent Tech Guardian" in completed.stdout
    assert "--state-file" in completed.stdout
    assert "--status-page" in completed.stdout


def test_cli_rejects_missing_required_output_paths_without_network():
    completed = invoke()
    assert completed.returncode == 2
    assert "usage:" in completed.stderr.lower()
    assert "--state-file" in completed.stderr
    assert "--status-page" in completed.stderr
