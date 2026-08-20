#!/usr/bin/env python3
"""Secondary freshness watchdog for the external Agent Tech Guardian.

Silent while the independent GitHub monitor is fresh. Prints exactly one alert
on stale/unreadable state and one recovery after freshness returns. Hermes cron
delivers non-empty stdout verbatim; no LLM is involved.
"""
from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ISSUE_API = "https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/1"
DEFAULT_STATE = Path.home() / ".hermes/state/agent-tech-guardian-heartbeat.json"
STALE_AFTER_SECONDS = 15 * 60


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def fetch_guardian_state(*, open_url=urllib.request.urlopen) -> dict:
    request = urllib.request.Request(
        ISSUE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Agent-Tech-Guardian-Heartbeat/1.0"},
    )
    issue = None
    for attempt in range(2):
        try:
            with open_url(request, timeout=20) as response:
                issue = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if attempt == 0 and exc.code in {502, 503, 504}:
                continue
            raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == 0:
                continue
            raise
    assert issue is not None
    state = json.loads(issue["body"])
    if not isinstance(state, dict) or not isinstance(state.get("checked_at"), str):
        raise ValueError("invalid guardian state")
    return state


def load_local(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def save_local(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def run_once(*, now: datetime | None = None, state_path: Path = DEFAULT_STATE, fetch: Callable[[], dict] = fetch_guardian_state) -> None:
    now = (now or utc_now()).astimezone(timezone.utc)
    previous = load_local(state_path)
    unhealthy_reason = ""
    checked_at = ""
    try:
        guardian = fetch()
        checked_at = str(guardian["checked_at"])
        age_seconds = (now - parse_utc(checked_at)).total_seconds()
        if age_seconds > STALE_AFTER_SECONDS:
            unhealthy_reason = "stale"
    except Exception:
        unhealthy_reason = "unreadable"

    was_unhealthy = bool(previous.get("unhealthy"))
    is_unhealthy = bool(unhealthy_reason)
    if is_unhealthy and not was_unhealthy:
        if unhealthy_reason == "stale":
            print(
                "🔴 Agent Tech Guardian heartbeat is stale. "
                f"The external five-minute monitor last checked at {checked_at}. "
                "The status board may be showing old information."
            )
        else:
            print(
                "🔴 Agent Tech Guardian heartbeat could not be read. "
                "The external monitor state is unavailable; the status board may be stale."
            )
    elif not is_unhealthy and was_unhealthy:
        print(
            "✅ Agent Tech Guardian heartbeat recovered. "
            f"The external monitor is updating again (last check {checked_at})."
        )
    save_local(state_path, {"unhealthy": is_unhealthy, "reason": unhealthy_reason, "checked_at": checked_at})


if __name__ == "__main__":
    run_once()
