import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "hermes" / "jet_broker_guardian_heartbeat.py"
spec = importlib.util.spec_from_file_location("jet_broker_heartbeat", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_probe_requires_app_gateway_model_and_exact_completion(monkeypatch):
    calls = []

    def fake_request(url, *, token="", payload=None):
        calls.append((url, bool(token), payload is not None))
        if url.endswith("broker.getjetai.com/health"):
            return {"status": "ok", "deployment_locked": False, "source_record_count": 2067}
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/v1/models"):
            return {"data": [{"id": "brokercompliance"}]}
        return {"choices": [{"message": {"content": "JET_BROKER_SYNTHETIC_OK"}}]}

    monkeypatch.setattr(module, "request_json", fake_request)
    payload = module.build_payload("secret", now="2026-08-25T01:00:00Z")

    assert payload == {
        "schema_version": 1,
        "producer_id": "jet-broker-mac-synthetic",
        "observed_at": "2026-08-25T01:00:00Z",
        "app_healthy": True,
        "gateway_healthy": True,
        "model_advertised": True,
        "completion_ok": True,
    }
    assert len(calls) == 4


def test_failed_completion_is_published_as_false(monkeypatch):
    def fake_request(url, *, token="", payload=None):
        if url.endswith("broker.getjetai.com/health"):
            return {"status": "ok", "deployment_locked": False, "source_record_count": 2067}
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/v1/models"):
            return {"data": [{"id": "brokercompliance"}]}
        return {"choices": [{"message": {"content": "wrong"}}]}

    monkeypatch.setattr(module, "request_json", fake_request)
    assert module.build_payload("secret", now="2026-08-25T01:00:00Z")["completion_ok"] is False


def test_publisher_uses_sanitized_exact_payload():
    payload = {
        "schema_version": 1,
        "producer_id": "jet-broker-mac-synthetic",
        "observed_at": "2026-08-25T01:00:00Z",
        "app_healthy": True,
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