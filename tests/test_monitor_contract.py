"""Executable endpoint and journey contracts for Agent Tech Guardian v1."""

from __future__ import annotations

import copy
import json

import pytest

from conftest import FakeResponse, run_monitor


def system(report, name: str):
    return report["systems"][name]


def test_all_four_system_journeys_are_operational(all_healthy_script):
    report, transport, state, notifier = run_monitor(all_healthy_script)

    assert report["overall"] == "operational"
    assert set(report["systems"]) == {"jetai", "matchmaker", "jet_center", "renee_todo"}
    assert {entry["state"] for entry in report["systems"].values()} == {"operational"}
    assert report["checked_at"] == "2026-08-20T12:00:00Z"
    assert len(transport.calls) == 8
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
    ):
        script[key] = [FakeResponse(500, "failed")]

    report, _, _, _ = run_monitor(script)

    assert report["overall"] == "outage"
    assert {entry["state"] for entry in report["systems"].values()} == {"outage"}


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
