# Agent Tech Guardian v1 Contract

## Outcome

Detect agent-facing availability failures before ordinary users report them by testing the public UI and launch contracts from an independent control plane.

## Prior capability and gap

Hermes Ops monitors scheduled jobs, APIs, queues, delivery, and local infrastructure. It does not continuously exercise the same public login and cross-application launch paths agents use. On 2026-08-20 MatchMaker's backend health remained green while its direct Google callback returned `Forbidden`; the missing UI journey check allowed the failure to reach an agent first.

## Failure-domain boundary

- The primary runner is GitHub Actions, outside Hermes, Renee's Mac, Railway-hosted applications, and the MatchMaker host.
- The repository contains no production credentials.
- Monitored applications are read-only targets. The off-Mac Guardian never sends forms, creates records, invokes model inference, advances queues, restarts services, or changes application state. The Mac-side Jet Broker producer may invoke only the fixed, non-business synthetic completion defined below; it has no application mutation tools or user data.
- Discord delivery uses an encrypted GitHub Actions secret.
- Public status output contains system names, state, timestamps, bounded reason codes, and response timing only—no tokens, cookies, query credentials, user identity, HTML dumps, or stack traces.

## V1 systems and exact journeys

1. **JetAI**
   - `GET https://app.getjetai.com/health` → HTTP 200 JSON `status=healthy`.
   - `GET https://app.getjetai.com/login` → HTTP 200 and title `Sign in to JetAI`.
2. **Jet Broker**
   - Mac-side deterministic producer verifies `https://broker.getjetai.com/health` is unlocked with a nonempty corpus.
   - Authenticated `GET http://127.0.0.1:18765/health` requires `status=ok`.
   - Authenticated `GET /v1/models` requires the dedicated `brokercompliance` route.
   - Authenticated `POST /v1/chat/completions` requires an exact harmless synthetic marker from the OAuth-backed model.
   - Only four booleans and a timestamp are published to the Guardian issue; no prompt, answer, token, user, or corpus data leaves the Mac.
3. **MatchMaker**
   - `GET https://matchmakerre.com/api/health` → HTTP 200 JSON `status=healthy`, `database=connected`.
   - No-follow `GET https://matchmakerre.com/login` → HTTP 302 with exact `Location: https://app.getjetai.com/launch/matchmaker`.
4. **Jet Center**
   - `GET https://web-production-1adf7.up.railway.app/health` → HTTP 200 JSON `status=ok`.
   - `GET https://web-production-1adf7.up.railway.app/login` → HTTP 200 and title `Sign In — Jet Center`.
5. **Renee TO-DO**
   - `GET https://ops.reneedelia.com/` → HTTP 200 and title `Renee's Command Center`.
   - `GET https://ops.reneedelia.com/api/data` → HTTP 200 and a valid JSON object.
6. **Offers Out**
   - `GET https://api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/8` → HTTP 200.
   - The issue body must be the exact PII-free heartbeat schema for producer
     `offers-out-mac-poller`, show the production poller enabled, and be no more
     than 15 minutes old. The Guardian remains read-only and never advances the queue.

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
- The GitHub-hosted Guardian uses no LLM. The separate Mac producer performs one fixed Jet Broker synthetic completion every five minutes and publishes booleans only.
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
- No claim that the fixed synthetic completion proves authenticated user-role visibility or substantive answer quality; it proves app/gateway/model-route availability.

## Follow-on release

A separate, minimally entitled Synthetic Agent will cover authenticated role journeys and Chat AI response readiness only after its identity, permissions, zero-write constraints, and credential lifecycle are approved and tested independently.
