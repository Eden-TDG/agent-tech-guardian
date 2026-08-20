from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any, Callable

TRANSIENT_STATUSES = {502, 503, 504}
EXPECTED_MATCHMAKER_REDIRECT = "https://app.getjetai.com/launch/matchmaker"


@dataclass(frozen=True)
class ProbeFailure(Exception):
    system: str
    stage: str
    reason: str
    diagnostic: str


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _title(body: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
    return unescape(re.sub(r"\s+", " ", match.group(1)).strip()) if match else ""


def _headers(response: Any) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in (response.headers or {}).items()}


def _safe_diagnostic(reason: str, detail: str = "") -> str:
    safe = {
        "network_error": "read-only request failed after bounded retry",
        "unexpected_http_status": "unexpected HTTP status",
        "invalid_json": "response was not valid JSON",
        "unexpected_payload": "response payload did not match the health contract",
        "unexpected_title": "page title did not match the UI contract",
        "unexpected_redirect": "redirect contract mismatch",
    }.get(reason, "probe contract failed")
    return f"{safe}: {detail}" if detail and re.fullmatch(r"[0-9]{3}", detail) else safe


class Monitor:
    def __init__(self, *, transport: Any, clock: Any, state_store: Any, notifier: Any, sleep: Callable[[float], None] = time.sleep) -> None:
        self.transport = transport
        self.clock = clock
        self.state_store = state_store
        self.notifier = notifier
        self.sleep = sleep

    def _get(self, system: str, stage: str, url: str, *, follow_redirects: bool = True):
        for attempt in range(2):
            try:
                response = self.transport.get(url, follow_redirects=follow_redirects)
            except Exception:
                if attempt == 0:
                    continue
                raise ProbeFailure(system, stage, "network_error", _safe_diagnostic("network_error"))
            if response.status in TRANSIENT_STATUSES and attempt == 0:
                continue
            return response
        raise AssertionError("unreachable retry state")

    def _expect_status(self, system: str, stage: str, response: Any, expected: int = 200) -> None:
        if response.status != expected:
            raise ProbeFailure(system, stage, "unexpected_http_status", _safe_diagnostic("unexpected_http_status", str(response.status)))

    def _expect_json(self, system: str, stage: str, response: Any, predicate: Callable[[Any], bool]) -> None:
        self._expect_status(system, stage, response)
        try:
            payload = response.json()
        except Exception:
            raise ProbeFailure(system, stage, "invalid_json", _safe_diagnostic("invalid_json"))
        if not predicate(payload):
            raise ProbeFailure(system, stage, "unexpected_payload", _safe_diagnostic("unexpected_payload"))

    def _expect_title(self, system: str, stage: str, response: Any, expected: str) -> None:
        self._expect_status(system, stage, response)
        if _title(response.body) != expected:
            raise ProbeFailure(system, stage, "unexpected_title", _safe_diagnostic("unexpected_title"))

    def _probe_jetai(self) -> None:
        r = self._get("jetai", "health", "https://app.getjetai.com/health")
        self._expect_json("jetai", "health", r, lambda p: isinstance(p, dict) and p.get("status") == "healthy")
        r = self._get("jetai", "login", "https://app.getjetai.com/login")
        self._expect_title("jetai", "login", r, "Sign in to JetAI")

    def _probe_matchmaker(self) -> None:
        r = self._get("matchmaker", "health", "https://matchmakerre.com/api/health")
        self._expect_json("matchmaker", "health", r, lambda p: isinstance(p, dict) and p.get("status") == "healthy" and p.get("database") == "connected")
        r = self._get("matchmaker", "login", "https://matchmakerre.com/login", follow_redirects=False)
        if r.status != 302 or _headers(r).get("location") != EXPECTED_MATCHMAKER_REDIRECT:
            raise ProbeFailure("matchmaker", "login", "unexpected_redirect", _safe_diagnostic("unexpected_redirect"))

    def _probe_jet_center(self) -> None:
        base = "https://web-production-1adf7.up.railway.app"
        r = self._get("jet_center", "health", base + "/health")
        self._expect_json("jet_center", "health", r, lambda p: isinstance(p, dict) and p.get("status") == "ok")
        r = self._get("jet_center", "login", base + "/login")
        self._expect_title("jet_center", "login", r, "Sign In — Jet Center")

    def _probe_renee_todo(self) -> None:
        base = "https://ops.reneedelia.com"
        r = self._get("renee_todo", "homepage", base + "/")
        self._expect_title("renee_todo", "homepage", r, "Renee's Command Center")
        r = self._get("renee_todo", "api_data", base + "/api/data")
        self._expect_json("renee_todo", "api_data", r, lambda p: isinstance(p, dict))

    def run(self) -> dict[str, Any]:
        checked_at = _iso(self.clock.now())
        previous = self.state_store.load()
        previous_systems = previous.get("systems", {}) if isinstance(previous.get("systems", {}), dict) else {}
        incidents = previous.get("incidents", {}) if isinstance(previous.get("incidents", {}), dict) else {}
        definitions = (
            ("jetai", "JetAI", self._probe_jetai),
            ("matchmaker", "MatchMaker", self._probe_matchmaker),
            ("jet_center", "Jet Center", self._probe_jet_center),
            ("renee_todo", "Renee TO-DO", self._probe_renee_todo),
        )
        systems: dict[str, dict[str, Any]] = {}
        for key, display_name, probe in definitions:
            previous_success = previous_systems.get(key, {}).get("last_successful_journey")
            try:
                probe()
                systems[key] = {"display_name": display_name, "state": "operational", "stage": None, "reason": None, "diagnostic": "", "last_successful_journey": checked_at}
                incident = incidents.pop(key, None)
                if incident and incident.get("alerted"):
                    self.notifier.send({"type": "recovery", "system": key, "display_name": display_name})
            except ProbeFailure as failure:
                systems[key] = {"display_name": display_name, "state": "outage", "stage": failure.stage, "reason": failure.reason, "diagnostic": failure.diagnostic, "last_successful_journey": previous_success}
                signature = {"system": key, "stage": failure.stage, "reason": failure.reason}
                prior = incidents.get(key, {})
                if prior.get("signature") == signature:
                    consecutive = int(prior.get("consecutive_runs", 0)) + 1
                    alerted = bool(prior.get("alerted"))
                else:
                    consecutive = 1
                    alerted = False
                incident = {"signature": signature, "consecutive_runs": consecutive, "alerted": alerted, "first_seen": prior.get("first_seen", checked_at) if prior.get("signature") == signature else checked_at, "last_seen": checked_at}
                if consecutive >= 2 and not alerted:
                    self.notifier.send({"type": "alert", "system": key, "display_name": display_name, "stage": failure.stage, "reason": failure.reason, "signature": signature})
                    incident["alerted"] = True
                incidents[key] = incident
        outage_count = sum(1 for item in systems.values() if item["state"] == "outage")
        overall = "operational" if outage_count == 0 else ("outage" if outage_count == len(systems) else "degraded")
        report = {"overall": overall, "checked_at": checked_at, "systems": systems}
        self.state_store.save({**report, "incidents": incidents})
        return report
