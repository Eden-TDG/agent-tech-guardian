"""Offline acceptance-test fakes for Agent Tech Guardian v1."""

from __future__ import annotations

import copy
import importlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest


@dataclass(frozen=True)
class FakeResponse:
    status: int
    body: str = ""
    headers: dict[str, str] | None = None

    def json(self) -> Any:
        return json.loads(self.body)


class FakeTransport:
    """Scripted GET-only transport; an unexpected request fails the test."""

    def __init__(self, scripted: dict[tuple[str, bool], list[Any]]) -> None:
        self.scripted = {key: list(values) for key, values in scripted.items()}
        self.calls: list[tuple[str, str, bool]] = []

    def get(self, url: str, *, follow_redirects: bool = True) -> FakeResponse:
        self.calls.append(("GET", url, follow_redirects))
        key = (url, follow_redirects)
        if key not in self.scripted or not self.scripted[key]:
            raise AssertionError(f"unexpected or exhausted GET: {key!r}")
        outcome = self.scripted[key].pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def __getattr__(self, name: str) -> Any:
        if name.lower() in {"post", "put", "patch", "delete"}:
            raise AssertionError(f"monitor attempted forbidden mutation: {name.upper()}")
        raise AttributeError(name)


class FakeClock:
    def __init__(self, *moments: datetime) -> None:
        self._moments = list(moments) or [datetime(2026, 8, 20, 12, tzinfo=timezone.utc)]

    def now(self) -> datetime:
        if len(self._moments) > 1:
            return self._moments.pop(0)
        return self._moments[0]


class FakeStateStore:
    """A JSON-boundary fake: every read/write is copied through JSON."""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self.value = self._round_trip(initial or {})
        self.saves: list[dict[str, Any]] = []

    @staticmethod
    def _round_trip(value: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(value))

    def load(self) -> dict[str, Any]:
        return self._round_trip(self.value)

    def save(self, value: dict[str, Any]) -> None:
        self.value = self._round_trip(value)
        self.saves.append(copy.deepcopy(self.value))


class FakeNotifier:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def send(self, event: dict[str, Any]) -> None:
        self.events.append(json.loads(json.dumps(event)))


def prospective(module_name: str, symbol: str) -> Any:
    """Resolve wished-for production APIs without breaking collection."""
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name or module_name.startswith(f"{exc.name}."):
            pytest.fail(f"RED: missing production module {module_name}", pytrace=False)
        raise
    if not hasattr(module, symbol):
        pytest.fail(f"RED: missing production symbol {module_name}.{symbol}", pytrace=False)
    return getattr(module, symbol)


@pytest.fixture
def all_healthy_script() -> dict[tuple[str, bool], list[FakeResponse]]:
    return {
        ("https://app.getjetai.com/health", True): [
            FakeResponse(200, '{"status":"healthy"}', {"Content-Type": "application/json"})
        ],
        ("https://app.getjetai.com/login", True): [
            FakeResponse(200, "<html><title>Sign in to JetAI</title></html>")
        ],
        ("https://matchmakerre.com/api/health", True): [
            FakeResponse(200, '{"status":"healthy","database":"connected"}')
        ],
        ("https://matchmakerre.com/login", False): [
            FakeResponse(302, "", {"Location": "https://app.getjetai.com/launch/matchmaker"})
        ],
        ("https://web-production-1adf7.up.railway.app/health", True): [
            FakeResponse(200, '{"status":"ok"}')
        ],
        ("https://web-production-1adf7.up.railway.app/login", True): [
            FakeResponse(200, "<html><title>Sign In — Jet Center</title></html>")
        ],
        ("https://ops.reneedelia.com/", True): [
            FakeResponse(200, "<html><title>Renee's Command Center</title></html>")
        ],
        ("https://ops.reneedelia.com/api/data", True): [
            FakeResponse(200, '{"todo":[]}')
        ],
        ("https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/8", True): [
            FakeResponse(200, json.dumps({"body": json.dumps({
                "schema_version": 1,
                "producer_id": "offers-out-mac-poller",
                "observed_at": "2026-08-20T11:58:00Z",
                "poller_last_run_at": "2026-08-20T11:57:00Z",
                "poller_enabled": True,
            })}))
        ],
    }


def run_monitor(
    script: dict[tuple[str, bool], list[Any]],
    *,
    state: FakeStateStore | None = None,
    notifier: FakeNotifier | None = None,
    clock: FakeClock | None = None,
):
    monitor_type = prospective("agent_tech_guardian.monitor", "Monitor")
    transport = FakeTransport(script)
    state = state or FakeStateStore()
    notifier = notifier or FakeNotifier()
    clock = clock or FakeClock()
    monitor = monitor_type(
        transport=transport,
        clock=clock,
        state_store=state,
        notifier=notifier,
    )
    report = monitor.run()
    return report, transport, state, notifier
