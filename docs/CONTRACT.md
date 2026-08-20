# Agent Tech Guardian v1 Contract

## Outcome

Detect agent-facing availability failures before ordinary users report them by testing the public UI and launch contracts from an independent control plane.

## Prior capability and gap

Hermes Ops monitors scheduled jobs, APIs, queues, delivery, and local infrastructure. It does not continuously exercise the same public login and cross-application launch paths agents use. On 2026-08-20 MatchMaker's backend health remained green while its direct Google callback returned `Forbidden`; the missing UI journey check allowed the failure to reach an agent first.

## Failure-domain boundary

- The primary runner is GitHub Actions, outside Hermes, Renee's Mac, Railway-hosted applications, and the MatchMaker host.
- The repository contains no production credentials.
- Monitored applications are read-only targets. Guardian must never send forms, create records, invoke model inference, advance queues, restart services, or change application state.
- Discord delivery uses an encrypted GitHub Actions secret.
- Public status output contains system names, state, timestamps, bounded reason codes, and response timing only—no tokens, cookies, query credentials, user identity, HTML dumps, or stack traces.

## V1 systems and exact journeys

1. **JetAI**
   - `GET https://app.getjetai.com/health` → HTTP 200 JSON `status=healthy`.
   - `GET https://app.getjetai.com/login` → HTTP 200 and title `Sign in to JetAI`.
2. **MatchMaker**
   - `GET https://matchmakerre.com/api/health` → HTTP 200 JSON `status=healthy`, `database=connected`.
   - No-follow `GET https://matchmakerre.com/login` → HTTP 302 with exact `Location: https://app.getjetai.com/launch/matchmaker`.
3. **Jet Center**
   - `GET https://web-production-1adf7.up.railway.app/health` → HTTP 200 JSON `status=ok`.
   - `GET https://web-production-1adf7.up.railway.app/login` → HTTP 200 and title `Sign In — Jet Center`.
4. **Renee TO-DO**
   - `GET https://ops.reneedelia.com/` → HTTP 200 and title `Renee's Command Center`.
   - `GET https://ops.reneedelia.com/api/data` → HTTP 200 and a valid JSON object.

## Incident contract

- Each read-only HTTP boundary gets one bounded retry for transport errors and HTTP 502/503/504.
- Failures use stable `system:stage:reason` signatures. Volatile timestamps, durations, attempt counts, URLs with queries, and response bodies are excluded from signatures.
- A single failing run is `degraded` and does not page.
- Two consecutive completed monitor runs with the same signature create one incident and one Discord alert.
- Unchanged incidents remain silent.
- A different stable signature creates a changed incident notification.
- Recovery emits one message only when a failure was previously alerted.
- Healthy steady state is silent.

## Status surface

The static status page shows:

- overall `Operational`, `Degraded`, or `Outage`;
- state and last checked time per system;
- last successful complete journey per system;
- bounded current reason when unhealthy;
- update freshness.

## Scheduling

- Deterministic GitHub Actions schedule every five minutes, offset from the top-of-hour scheduler boundary.
- Manual workflow dispatch for controlled verification.
- No LLM calls.
- A separate deterministic Hermes heartbeat checks the external state every 15
  minutes. For stale state it performs one bounded GitHub workflow dispatch per
  stale timestamp and verifies `checked_at` advancement before alerting; unreadable
  state remains fail-closed. It alerts once after exhausted repair, then once on recovery.
- A definitive anonymous GitHub API quota exhaustion may use the local authenticated
  GitHub CLI only to read the same issue state. Other 403s and invalid payloads do not fall back.

## Explicit non-goals for v1

- No permanent authentication bypass.
- No use of Renee's personal login.
- No live business mutation.
- No automatic service restart.
- No claim that public pre-auth checks prove authenticated role visibility or AI answer quality.

## Follow-on release

A separate, minimally entitled Synthetic Agent will cover authenticated role journeys and Chat AI response readiness only after its identity, permissions, zero-write constraints, and credential lifecycle are approved and tested independently.
