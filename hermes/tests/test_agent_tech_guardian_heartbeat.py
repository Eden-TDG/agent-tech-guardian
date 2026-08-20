from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "agent_tech_guardian_heartbeat.py"
spec = importlib.util.spec_from_file_location("guardian_heartbeat", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def state(checked_at: datetime, overall: str = "operational") -> dict:
    return {"checked_at": checked_at.isoformat().replace("+00:00", "Z"), "overall": overall}


def test_fresh_heartbeat_is_silent(tmp_path, capsys):
    now = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
    module.run_once(now=now, state_path=tmp_path / "state.json", fetch=lambda: state(now - timedelta(minutes=5)))
    assert capsys.readouterr().out == ""


def test_stale_heartbeat_alerts_once_then_deduplicates(tmp_path, capsys):
    now = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
    path = tmp_path / "state.json"
    stale = lambda: state(now - timedelta(minutes=20))
    module.run_once(now=now, state_path=path, fetch=stale)
    first = capsys.readouterr().out
    assert "Agent Tech Guardian heartbeat is stale" in first
    module.run_once(now=now + timedelta(minutes=5), state_path=path, fetch=stale)
    assert capsys.readouterr().out == ""


def test_recovery_message_emits_once(tmp_path, capsys):
    now = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
    path = tmp_path / "state.json"
    module.run_once(now=now, state_path=path, fetch=lambda: state(now - timedelta(minutes=20)))
    capsys.readouterr()
    module.run_once(now=now, state_path=path, fetch=lambda: state(now))
    assert "heartbeat recovered" in capsys.readouterr().out
    module.run_once(now=now, state_path=path, fetch=lambda: state(now))
    assert capsys.readouterr().out == ""


def test_fetch_failure_is_sanitized_and_deduplicated(tmp_path, capsys):
    def broken():
        raise RuntimeError("secret-token-value")
    module.run_once(now=datetime(2026, 8, 20, tzinfo=timezone.utc), state_path=tmp_path / "state.json", fetch=broken)
    output = capsys.readouterr().out
    assert "could not be read" in output
    assert "secret-token-value" not in output
