"""Persistence, alert debounce, suppression, and recovery acceptance tests."""

from __future__ import annotations

import copy
from datetime import datetime, timezone

from conftest import FakeClock, FakeNotifier, FakeResponse, FakeStateStore, run_monitor


JET_HEALTH = ("https://app.getjetai.com/health", True)


def failing(script, response=None):
    result = copy.deepcopy(script)
    result[JET_HEALTH] = [response or FakeResponse(503, "unavailable")] * 2
    return result


def test_first_completed_failure_is_persisted_but_not_alerted(all_healthy_script):
    state = FakeStateStore()
    notifier = FakeNotifier()

    report, _, state, notifier = run_monitor(failing(all_healthy_script), state=state, notifier=notifier)

    assert report["systems"]["jetai"]["state"] == "outage"
    assert notifier.events == []
    incident = state.value["incidents"]["jetai"]
    assert incident["consecutive_runs"] == 1
    assert incident["alerted"] is False
    assert incident["signature"] == {"system": "jetai", "stage": "health", "reason": "unexpected_http_status"}


def test_same_failure_alerts_on_second_consecutive_completed_run(all_healthy_script):
    state = FakeStateStore()
    notifier = FakeNotifier()
    run_monitor(failing(all_healthy_script), state=state, notifier=notifier)

    run_monitor(failing(all_healthy_script), state=state, notifier=notifier)

    assert len(notifier.events) == 1
    assert notifier.events[0]["type"] == "alert"
    assert notifier.events[0]["signature"] == {
        "system": "jetai",
        "stage": "health",
        "reason": "unexpected_http_status",
    }
    assert state.value["incidents"]["jetai"]["alerted"] is True


def test_unchanged_alerted_incident_is_suppressed(all_healthy_script):
    state = FakeStateStore()
    notifier = FakeNotifier()
    for _ in range(3):
        run_monitor(failing(all_healthy_script), state=state, notifier=notifier)

    assert [event["type"] for event in notifier.events] == ["alert"]


def test_changed_stable_failure_signature_restarts_debounce(all_healthy_script):
    state = FakeStateStore()
    notifier = FakeNotifier()
    run_monitor(failing(all_healthy_script), state=state, notifier=notifier)
    changed = failing(all_healthy_script, FakeResponse(200, "not-json"))

    run_monitor(changed, state=state, notifier=notifier)

    assert notifier.events == []
    incident = state.value["incidents"]["jetai"]
    assert incident["consecutive_runs"] == 1
    assert incident["signature"]["reason"] == "invalid_json"


def test_recovery_emitted_once_after_alerted_incident(all_healthy_script):
    state = FakeStateStore()
    notifier = FakeNotifier()
    run_monitor(failing(all_healthy_script), state=state, notifier=notifier)
    run_monitor(failing(all_healthy_script), state=state, notifier=notifier)

    run_monitor(copy.deepcopy(all_healthy_script), state=state, notifier=notifier)
    run_monitor(copy.deepcopy(all_healthy_script), state=state, notifier=notifier)

    assert [event["type"] for event in notifier.events] == ["alert", "recovery"]
    assert notifier.events[-1]["system"] == "jetai"
    assert "jetai" not in state.value.get("incidents", {})


def test_unalerted_single_failure_does_not_emit_recovery(all_healthy_script):
    state = FakeStateStore()
    notifier = FakeNotifier()
    run_monitor(failing(all_healthy_script), state=state, notifier=notifier)

    run_monitor(copy.deepcopy(all_healthy_script), state=state, notifier=notifier)

    assert notifier.events == []


def test_last_successful_journey_survives_a_later_failure(all_healthy_script):
    state = FakeStateStore()
    notifier = FakeNotifier()
    first_time = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
    later_time = datetime(2026, 8, 20, 12, 5, tzinfo=timezone.utc)
    run_monitor(copy.deepcopy(all_healthy_script), state=state, notifier=notifier, clock=FakeClock(first_time))

    report, _, state, _ = run_monitor(
        failing(all_healthy_script), state=state, notifier=notifier, clock=FakeClock(later_time)
    )

    assert report["systems"]["jetai"]["last_successful_journey"] == "2026-08-20T12:00:00Z"
    assert state.value["systems"]["jetai"]["last_successful_journey"] == "2026-08-20T12:00:00Z"
