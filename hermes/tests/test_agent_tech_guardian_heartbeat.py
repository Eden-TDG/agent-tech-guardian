from __future__ import annotations

import importlib.util
import json
import urllib.error
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
    recoveries = []
    repair = lambda checked_at, _fetch: recoveries.append(checked_at) or None
    module.run_once(now=now, state_path=path, fetch=stale, repair=repair)
    first = capsys.readouterr().out
    assert "Agent Tech Guardian heartbeat is stale" in first
    module.run_once(now=now + timedelta(minutes=5), state_path=path, fetch=stale, repair=repair)
    assert capsys.readouterr().out == ""
    assert len(recoveries) == 1


def test_recovery_message_emits_once(tmp_path, capsys):
    now = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
    path = tmp_path / "state.json"
    no_repair = lambda _checked_at, _fetch: None
    module.run_once(
        now=now,
        state_path=path,
        fetch=lambda: state(now - timedelta(minutes=20)),
        repair=no_repair,
    )
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


def test_stale_heartbeat_dispatches_once_and_stays_silent_when_repair_advances_state(tmp_path, capsys):
    now = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
    stale_state = state(now - timedelta(minutes=20))
    calls = []

    def repair(checked_at, fetch):
        calls.append((checked_at, fetch()))
        return state(now)

    path = tmp_path / "state.json"
    module.run_once(now=now, state_path=path, fetch=lambda: stale_state, repair=repair)

    assert capsys.readouterr().out == ""
    assert calls == [(stale_state["checked_at"], stale_state)]
    assert json.loads(path.read_text())["unhealthy"] is False


def test_alerted_stale_heartbeat_emits_recovery_when_dispatch_repairs_it(tmp_path, capsys):
    now = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"unhealthy": True, "reason": "stale"}))

    module.run_once(
        now=now,
        state_path=path,
        fetch=lambda: state(now - timedelta(minutes=20)),
        repair=lambda _checked_at, _fetch: state(now),
    )

    assert "heartbeat recovered" in capsys.readouterr().out


def test_unreadable_heartbeat_does_not_dispatch_monitor(tmp_path, capsys):
    calls = []

    def broken():
        raise RuntimeError("unavailable")

    module.run_once(
        now=datetime(2026, 8, 20, tzinfo=timezone.utc),
        state_path=tmp_path / "state.json",
        fetch=broken,
        repair=lambda *_args: calls.append(True),
    )

    assert calls == []
    assert "could not be read" in capsys.readouterr().out


def test_repair_dispatches_exact_workflow_and_requires_checked_at_to_advance():
    stale = "2026-08-20T15:00:00Z"
    advanced = state(datetime(2026, 8, 20, 15, 20, tzinfo=timezone.utc))
    fetched = iter([{"checked_at": stale}, advanced])
    commands = []
    sleeps = []

    def runner(command, **kwargs):
        commands.append((command, kwargs))

    result = module.repair_stale_monitor(
        stale,
        lambda: next(fetched),
        runner=runner,
        sleep=lambda seconds: sleeps.append(seconds),
        poll_attempts=2,
    )

    assert result == advanced
    assert commands[0][0] == [
        "gh", "workflow", "run", "monitor.yml",
        "--repo", "Eden-TDG/agent-tech-guardian",
        "--ref", "main",
    ]
    assert commands[0][1]["check"] is True
    assert sleeps == [5, 5]


class FakeHTTPResponse:
    def __init__(self, body: dict):
        self.body = body

    def read(self):
        return json.dumps(self.body)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_guardian_state_fetch_retries_one_transport_timeout():
    calls = []
    issue = {"body": json.dumps(state(datetime(2026, 8, 20, tzinfo=timezone.utc)))}

    def open_url(_request, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise TimeoutError("temporary")
        return FakeHTTPResponse(issue)

    result = module.fetch_guardian_state(open_url=open_url)
    assert result["overall"] == "operational"
    assert calls == [20, 20]


def test_guardian_state_fetch_does_not_retry_invalid_payload():
    calls = []

    def open_url(_request, timeout):
        calls.append(timeout)
        return FakeHTTPResponse({"body": "not-json"})

    try:
        module.fetch_guardian_state(open_url=open_url)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("invalid payload must fail closed")
    assert calls == [20]
