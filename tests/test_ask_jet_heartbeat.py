import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "hermes" / "ask_jet_guardian_heartbeat.py"
spec = importlib.util.spec_from_file_location("ask_jet_heartbeat", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_probe_requires_gateway_model_and_exact_completion(monkeypatch):
    calls = []

    def fake_request(url, *, token="", payload=None):
        calls.append((url, bool(token), payload is not None))
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/v1/models"):
            return {"data": [{"id": "ask-jet"}]}
        return {"choices": [{"message": {"content": "ASK_JET_SYNTHETIC_OK"}}]}

    monkeypatch.setattr(module, "request_json", fake_request)
    payload = module.build_payload("secret", now="2026-08-25T01:00:00Z")

    assert payload == {
        "schema_version": 1,
        "producer_id": "ask-jet-mac-synthetic",
        "observed_at": "2026-08-25T01:00:00Z",
        "gateway_healthy": True,
        "model_advertised": True,
        "completion_ok": True,
    }
    assert len(calls) == 3


def test_failed_completion_is_published_as_false(monkeypatch):
    def fake_request(url, *, token="", payload=None):
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/v1/models"):
            return {"data": [{"id": "ask-jet"}]}
        return {"choices": [{"message": {"content": "wrong"}}]}

    monkeypatch.setattr(module, "request_json", fake_request)
    assert module.build_payload("secret", now="2026-08-25T01:00:00Z")["completion_ok"] is False


def test_publisher_uses_sanitized_exact_payload():
    payload = {
        "schema_version": 1,
        "producer_id": "ask-jet-mac-synthetic",
        "observed_at": "2026-08-25T01:00:00Z",
        "gateway_healthy": True,
        "model_advertised": True,
        "completion_ok": True,
    }
    calls = []

    class Result:
        returncode = 0

    module.publish(payload, runner=lambda *a, **k: calls.append((a, k)) or Result())
    command = calls[0][0][0]
    assert command[:6] == ["gh", "issue", "edit", module.GUARDIAN_ISSUE, "--repo", module.GUARDIAN_REPOSITORY]
    assert json.loads(command[-1]) == payload


def result(returncode: int, stderr: str = ""):
    return SimpleNamespace(returncode=returncode, stdout="", stderr=stderr)


def test_publish_retries_transient_github_failure_then_recovers():
    calls = []
    outcomes = iter([result(1, "HTTP 502: Bad Gateway"), result(0)])
    sleeps = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return next(outcomes)

    module.publish({}, runner=runner, sleeper=sleeps.append, retry_delays=(1, 2))

    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert sleeps == [1]


def test_publish_retries_subprocess_timeout_then_recovers():
    calls = []
    sleeps = []

    def runner(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise module.subprocess.TimeoutExpired(command, kwargs["timeout"])
        return result(0)

    module.publish({}, runner=runner, sleeper=sleeps.append, retry_delays=(1, 2))

    assert len(calls) == 2
    assert sleeps == [1]


def test_publish_does_not_retry_nontransient_github_failure():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return result(1, "HTTP 401: Bad credentials")

    with pytest.raises(RuntimeError, match="github_publish_failed.*HTTP 401: Bad credentials"):
        module.publish({}, runner=runner, sleeper=lambda _delay: None, retry_delays=(1, 2))

    assert len(calls) == 1


def test_publish_exhaustion_preserves_bounded_causal_diagnostic():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return result(1, "connection reset by peer " + "x" * 1000)

    with pytest.raises(RuntimeError) as captured:
        module.publish({}, runner=runner, sleeper=lambda _delay: None, retry_delays=(1, 2))

    message = str(captured.value)
    assert len(calls) == 3
    assert message.startswith("github_publish_failed after 3 attempts: connection reset by peer")
    assert len(message) <= 300
