#!/usr/bin/env python3
"""Publish a sanitized Ask Jet synthetic model-journey heartbeat."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path.home() / ".hermes" / "scripts"
GUARDIAN_REPOSITORY = "Eden-TDG/agent-tech-guardian"
GUARDIAN_ISSUE = "11"
GATEWAY = "https://edens-imac.tail06fe59.ts.net:8443/askjet"
EXPECTED_MODEL = "ask-jet"
MARKER = "ASK_JET_SYNTHETIC_OK"
HEALTHY_COMPLETION_MARKERS = {
    MARKER,
    "ASK_JET_COMPLIANCE_OK",
    "ASK_COMPLETED_OK",
}
FALLBACK_CHALLENGE = "Synthetic completion challenge. What is 2 plus 2? Reply with only the number."
TRANSIENT_HTTP_STATUSES = {502, 503, 504}
RETRY_DELAYS = (1, 2)
GITHUB_TRANSIENT_MARKERS = (
    "502", "503", "504", "bad gateway", "service unavailable",
    "gateway timeout", "connection reset", "connection refused",
    "connection timed out", "context deadline exceeded", "eof",
    "network is unreachable", "temporary failure", "tls handshake timeout",
)


def request_json(url: str, *, token: str = "", payload: dict | None = None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    method = "GET"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    attempts = len(RETRY_DELAYS) + 1
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in TRANSIENT_HTTP_STATUSES or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, ConnectionError, socket.timeout, TimeoutError):
            if attempt == attempts - 1:
                raise
        time.sleep(RETRY_DELAYS[attempt])
    raise AssertionError("unreachable retry state")


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _completion_content(response: dict) -> str:
    content = response["choices"][0]["message"]["content"]
    return content.strip() if isinstance(content, str) else ""


def completion_path_healthy(token: str) -> bool:
    """Verify one real completion, with a bounded contract-drift fallback.

    Ask Jet's compliance layer may intentionally replace an arbitrary requested
    marker with one of its own exact healthy markers. If that contract evolves,
    one independent arithmetic challenge proves the same model path without
    accepting arbitrary prose or substrings as success.
    """
    try:
        primary = request_json(
            GATEWAY + "/v1/chat/completions",
            token=token,
            payload={
                "model": EXPECTED_MODEL,
                "stream": False,
                "messages": [{
                    "role": "user",
                    "content": "Synthetic monitoring check. Reply with exactly " + MARKER + " and nothing else.",
                }],
            },
        )
        if _completion_content(primary) in HEALTHY_COMPLETION_MARKERS:
            return True
    except Exception:
        pass

    try:
        fallback = request_json(
            GATEWAY + "/v1/chat/completions",
            token=token,
            payload={
                "model": EXPECTED_MODEL,
                "stream": False,
                "messages": [{"role": "user", "content": FALLBACK_CHALLENGE}],
            },
        )
        return _completion_content(fallback) == "4"
    except Exception:
        return False


def build_payload(token: str, *, now: str | None = None) -> dict:
    result = {
        "schema_version": 1,
        "producer_id": "ask-jet-mac-synthetic",
        "observed_at": now or _iso_now(),
        "gateway_healthy": False,
        "model_advertised": False,
        "completion_ok": False,
    }
    if not token:
        return result
    try:
        health = request_json(GATEWAY + "/health", token=token)
        result["gateway_healthy"] = isinstance(health, dict) and health.get("status") == "ok"
    except Exception:
        return result
    try:
        models = request_json(GATEWAY + "/v1/models", token=token)
        result["model_advertised"] = any(
            isinstance(item, dict) and item.get("id") == EXPECTED_MODEL
            for item in (models.get("data", []) if isinstance(models, dict) else [])
        )
    except Exception:
        return result
    if not result["model_advertised"]:
        return result
    result["completion_ok"] = completion_path_healthy(token)
    return result


def _bounded_detail(text: str) -> str:
    return " ".join((text or "unknown gh failure").split())[:240]


def _github_failure_is_transient(detail: str) -> bool:
    lowered = detail.lower()
    return any(marker in lowered for marker in GITHUB_TRANSIENT_MARKERS)


def publish(
    payload: dict,
    *,
    runner=subprocess.run,
    sleeper=time.sleep,
    retry_delays=RETRY_DELAYS,
) -> None:
    command = [
        "gh", "issue", "edit", GUARDIAN_ISSUE,
        "--repo", GUARDIAN_REPOSITORY,
        "--body", json.dumps(payload, sort_keys=True, separators=(",", ":")),
    ]
    attempts = len(retry_delays) + 1
    for attempt in range(attempts):
        try:
            completed = runner(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=45,
            )
        except subprocess.TimeoutExpired as exc:
            detail = _bounded_detail(f"gh command timed out after {exc.timeout} seconds")
            if attempt == attempts - 1:
                raise RuntimeError(
                    f"github_publish_failed after {attempt + 1} attempts: {detail}"
                ) from exc
            sleeper(retry_delays[attempt])
            continue
        if completed.returncode == 0:
            return
        detail = _bounded_detail(completed.stderr or completed.stdout)
        transient = _github_failure_is_transient(detail)
        if not transient or attempt == attempts - 1:
            raise RuntimeError(
                f"github_publish_failed after {attempt + 1} attempts: {detail}"
            )
        sleeper(retry_delays[attempt])
    raise AssertionError("unreachable GitHub publish retry state")


def main() -> int:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from vault_cache_reader import read_credential

    token = read_credential("__direct__", "", "ASK_JET_API_SERVER_KEY") or ""
    publish(build_payload(token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
