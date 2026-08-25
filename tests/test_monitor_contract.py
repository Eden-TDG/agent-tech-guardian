"""Executable endpoint and journey contracts for Agent Tech Guardian v1."""

from __future__ import annotations

import copy
import json

import pytest

from conftest import FakeResponse, run_monitor


def system(report, name: str):
    return report["systems"][name]


def test_all_seven_system_journeys_are_operational(all_healthy_script):
    report, transport, state, notifier = run_monitor(all_healthy_script)

    assert report["overall"] == "operational"
    assert set(report["systems"]) == {"jetai", "ask_jet", "jet_broker", "matchmaker", "jet_center", "renee_todo", "offers_out"}
    assert {entry["state"] for entry in report["systems"].values()} == {"operational"}
    assert report["checked_at"] == "2026-08-20T12:00:00Z"
    assert len(transport.calls) == 11
    assert notifier.events == []
    assert len(state.saves) == 1
    json.dumps(state.value)


@pytest.mark.parametrize(
    ("system_name", "url", "follow_redirects", "response", "stage", "reason"),
    [
        ("jetai", "https://app.getjetai.com/health", True, FakeResponse(200, '{"status":"down"}'), "health", "unexpected_payload"),
        ("jetai", "https://app.getjetai.com/login", True, FakeResponse(200, "<title>Welcome</title>"), "login", "unexpected_title"),
        ("matchmaker", "https://matchmakerre.com/api/health", True, FakeResponse(200, '{"status":"healthy","database":"offline"}'), "health", "unexpected_payload"),
        ("jet_center", "https://web-production-1adf7.up.railway.app/health", True, FakeResponse(200, '{"status":"healthy"}'), "health", "unexpected_payload"),
        ("jet_center", "https://web-production-1adf7.up.railway.app/login", True, FakeResponse(200, "<title>Sign In - Jet Center</title>"), "login", "unexpected_title"),
        ("renee_todo", "https://ops.reneedelia.com/", True, FakeResponse(200, "<title>Other</title>"), "homepage", "unexpected_title"),
        ("renee_todo", "https://ops.reneedelia.com/api/data", True, FakeResponse(200, "[]"), "api_data", "unexpected_payload"),
    ],
)
def test_contract_mismatch_has_stable_classification(
    all_healthy_script, system_name, url, follow_redirects, response, stage, reason
):
    script = copy.deepcopy(all_healthy_script)
    script[(url, follow_redirects)] = [response]

    report, _, _, _ = run_monitor(script)

    assert report["overall"] == "degraded"
    assert system(report, system_name)["state"] == "outage"
    assert system(report, system_name)["stage"] == stage
    assert system(report, system_name)["reason"] == reason
    assert isinstance(system(report, system_name)["diagnostic"], str)


def test_all_system_failures_make_overall_outage(all_healthy_script):
    script = copy.deepcopy(all_healthy_script)
    for key in (
        ("https://app.getjetai.com/health", True),
        ("https://matchmakerre.com/api/health", True),
        ("https://web-production-1adf7.up.railway.app/health", True),
        ("https://ops.reneedelia.com/", True),
        ("https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/8", True),
        ("https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/10", True),
        ("https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/11", True),
    ):
        script[key] = [FakeResponse(500, "failed")]

    report, _, _, _ = run_monitor(script)

    assert report["overall"] == "outage"
    assert {entry["state"] for entry in report["systems"].values()} == {"outage"}


def test_jet_broker_failed_completion_heartbeat_is_an_outage(all_healthy_script):
    script = copy.deepcopy(all_healthy_script)
    url = "https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/10"
    payload = {
        "schema_version": 1,
        "producer_id": "jet-broker-mac-synthetic",
        "observed_at": "2026-08-20T11:58:00Z",
        "app_healthy": True,
        "gateway_healthy": True,
        "model_advertised": True,
        "completion_ok": False,
    }
    script[(url, True)] = [FakeResponse(200, json.dumps({"body": json.dumps(payload)}))]

    report, _, _, _ = run_monitor(script)

    assert system(report, "jet_broker")["state"] == "outage"
    assert system(report, "jet_broker")["stage"] == "synthetic_heartbeat"
    assert system(report, "jet_broker")["reason"] == "completion_failed"


def test_jet_broker_stale_heartbeat_is_an_outage(all_healthy_script):
    script = copy.deepcopy(all_healthy_script)
    url = "https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/10"
    payload = {
        "schema_version": 1,
        "producer_id": "jet-broker-mac-synthetic",
        "observed_at": "2026-08-20T11:30:00Z",
        "app_healthy": True,
        "gateway_healthy": True,
        "model_advertised": True,
        "completion_ok": True,
    }
    script[(url, True)] = [FakeResponse(200, json.dumps({"body": json.dumps(payload)}))]

    report, _, _, _ = run_monitor(script)

    assert system(report, "jet_broker")["reason"] == "heartbeat_stale"


def test_ask_jet_failed_completion_heartbeat_is_an_outage(all_healthy_script):
    script = copy.deepcopy(all_healthy_script)
    url = "https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/11"
    payload = {
        "schema_version": 1,
        "producer_id": "ask-jet-mac-synthetic",
        "observed_at": "2026-08-20T11:58:00Z",
        "gateway_healthy": True,
        "model_advertised": True,
        "completion_ok": False,
    }
    script[(url, True)] = [FakeResponse(200, json.dumps({"body": json.dumps(payload)}))]

    report, _, _, _ = run_monitor(script)

    assert system(report, "ask_jet")["state"] == "outage"
    assert system(report, "ask_jet")["stage"] == "synthetic_heartbeat"
    assert system(report, "ask_jet")["reason"] == "completion_failed"


def test_ask_jet_stale_heartbeat_is_an_outage(all_healthy_script):
    script = copy.deepcopy(all_healthy_script)
    url = "https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/11"
    payload = {
        "schema_version": 1,
        "producer_id": "ask-jet-mac-synthetic",
        "observed_at": "2026-08-20T11:30:00Z",
        "gateway_healthy": True,
        "model_advertised": True,
        "completion_ok": True,
    }
    script[(url, True)] = [FakeResponse(200, json.dumps({"body": json.dumps(payload)}))]

    report, _, _, _ = run_monitor(script)

    assert system(report, "ask_jet")["reason"] == "heartbeat_stale"


def test_offers_out_stale_heartbeat_has_stable_sanitized_alert_signature(all_healthy_script):
    script = copy.deepcopy(all_healthy_script)
    url = "https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/8"
    stale = {
        "schema_version": 1,
        "producer_id": "offers-out-mac-poller",
        "observed_at": "2026-08-20T11:30:00Z",
        "poller_last_run_at": "2026-08-20T11:29:00Z",
        "poller_enabled": True,
    }
    script[(url, True)] = [FakeResponse(200, json.dumps({"body": json.dumps(stale)}))]

    report, _, _, _ = run_monitor(script)

    assert system(report, "offers_out") == {
        "display_name": "Offers Out",
        "state": "outage",
        "stage": "mac_heartbeat",
        "reason": "heartbeat_stale",
        "diagnostic": "sanitized Mac poller heartbeat is stale",
        "last_successful_journey": None,
    }


def test_synthetic_stale_offers_out_heartbeat_pages_test_notifier_after_two_runs(all_healthy_script):
    from conftest import FakeClock, FakeNotifier, FakeStateStore
    from datetime import datetime, timezone

    script = copy.deepcopy(all_healthy_script)
    url = "https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/8"
    body = json.dumps({
        "schema_version": 1,
        "producer_id": "offers-out-mac-poller",
        "observed_at": "2026-08-20T11:30:00Z",
        "poller_last_run_at": "2026-08-20T11:29:00Z",
        "poller_enabled": True,
    })
    script[(url, True)] = [FakeResponse(200, json.dumps({"body": body}))]
    state = FakeStateStore()
    notifier = FakeNotifier()
    first, _, state, notifier = run_monitor(script, state=state, notifier=notifier)
    assert first["systems"]["offers_out"]["reason"] == "heartbeat_stale"
    assert notifier.events == []

    second_script = copy.deepcopy(all_healthy_script)
    second_script[(url, True)] = [FakeResponse(200, json.dumps({"body": body}))]
    run_monitor(
        second_script,
        state=state,
        notifier=notifier,
        clock=FakeClock(datetime(2026, 8, 20, 12, 5, tzinfo=timezone.utc)),
    )
    assert notifier.events == [{
        "type": "alert",
        "system": "offers_out",
        "display_name": "Offers Out",
        "stage": "mac_heartbeat",
        "reason": "heartbeat_stale",
        "signature": {"system": "offers_out", "stage": "mac_heartbeat", "reason": "heartbeat_stale"},
    }]


def test_matchmaker_login_redirect_is_not_followed_and_location_is_exact(all_healthy_script):
    script = copy.deepcopy(all_healthy_script)
    script[("https://matchmakerre.com/login", False)] = [
        FakeResponse(302, "", {"Location": "https://app.getjetai.com/login"})
    ]

    report, transport, _, _ = run_monitor(script)

    assert system(report, "matchmaker")["stage"] == "login"
    assert system(report, "matchmaker")["reason"] == "unexpected_redirect"
    assert ("GET", "https://matchmakerre.com/login", False) in transport.calls
    assert ("GET", "https://app.getjetai.com/launch/matchmaker", True) not in transport.calls


@pytest.mark.parametrize("transient", [502, 503, 504])
def test_transient_http_status_is_retried_once(all_healthy_script, transient):
    script = copy.deepcopy(all_healthy_script)
    key = ("https://app.getjetai.com/health", True)
    script[key] = [FakeResponse(transient, "temporary"), FakeResponse(200, '{"status":"healthy"}')]

    report, transport, _, _ = run_monitor(script)

    assert system(report, "jetai")["state"] == "operational"
    assert [call for call in transport.calls if call[1] == key[0]] == [
        ("GET", key[0], True),
        ("GET", key[0], True),
    ]


def test_transient_network_exception_is_retried_once(all_healthy_script):
    script = copy.deepcopy(all_healthy_script)
    key = ("https://app.getjetai.com/health", True)
    script[key] = [TimeoutError("temporary timeout"), FakeResponse(200, '{"status":"healthy"}')]

    report, transport, _, _ = run_monitor(script)

    assert system(report, "jetai")["state"] == "operational"
    assert len([call for call in transport.calls if call[1] == key[0]]) == 2


def test_nontransient_http_failure_is_not_retried(all_healthy_script):
    script = copy.deepcopy(all_healthy_script)
    key = ("https://app.getjetai.com/health", True)
    script[key] = [FakeResponse(500, "failed"), FakeResponse(200, '{"status":"healthy"}')]

    report, transport, _, _ = run_monitor(script)

    assert system(report, "jetai")["reason"] == "unexpected_http_status"
    assert len([call for call in transport.calls if call[1] == key[0]]) == 1


def test_diagnostics_are_sanitized(all_healthy_script):
    script = copy.deepcopy(all_healthy_script)
    secret = "super-secret-token"
    key = ("https://app.getjetai.com/health", True)
    script[key] = [RuntimeError(f"request failed Authorization: Bearer {secret} https://host/path?token={secret}")] * 2

    report, _, state, _ = run_monitor(script)

    serialized = json.dumps({"report": report, "state": state.value})
    assert secret not in serialized
    assert "Authorization" not in serialized
    assert "?token=" not in serialized
    assert system(report, "jetai")["reason"] == "network_error"


def test_monitor_uses_get_only(all_healthy_script):
    _, transport, _, _ = run_monitor(all_healthy_script)
    assert {method for method, _, _ in transport.calls} == {"GET"}
