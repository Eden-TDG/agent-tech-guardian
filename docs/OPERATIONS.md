# Agent Tech Guardian Operations Runbook

## Production surfaces

| Surface | Location | Purpose |
|---|---|---|
| Status page | https://eden-tdg.github.io/agent-tech-guardian/ | Human availability view |
| Durable state | GitHub issue `Eden-TDG/agent-tech-guardian#1` | Machine-readable monitor and incident state |
| External runner | GitHub Actions workflow `Guardian Monitor` | Five-minute read-only synthetic checks |
| Incident channel | Discord `#automation-status` | First incident, changed signature, recovery, and heartbeat alerts |
| Secondary heartbeat | Hermes cron `3cf027636fc2` | Detect stale or unreadable external monitor state |

## Ownership and safety

- Operational owner: Renee / Jet automation operations.
- Guardian may issue only HTTP GET requests to monitored application surfaces.
- Guardian must not restart, reload, kill, or mutate any monitored service.
- A failed probe is evidence of a failed monitored journey, not permission to repair production automatically.
- Application credentials, cookies, OAuth sessions, and customer data must never enter the public repository, state issue, status page, diagnostics, or workflow logs.

## Normal operating contract

1. GitHub runs the monitor every five minutes on an offset schedule to avoid the busiest top-of-hour scheduler boundary.
2. One bounded retry absorbs a transient network, 502, 503, or 504 failure.
3. The first completed failed run persists a degraded state but sends no incident alert.
4. A second run with the same stable `system:stage:reason` signature sends one Discord alert.
5. Unchanged incidents remain silent.
6. A previously alerted incident sends one recovery message after the full journey passes.
7. The status page fails visibly closed when state is older than 15 minutes or cannot be read.
8. The secondary heartbeat checks every 15 minutes. When external state is stale, it dispatches the GitHub workflow once for that exact stale timestamp, waits for `checked_at` to advance, and remains silent if the repair succeeds. It alerts once only when dispatch/verification is exhausted or the state is unreadable, then once on recovery.
9. The heartbeat reads the public issue API first. Only a definitive anonymous GitHub quota exhaustion (`403` with `X-RateLimit-Remaining: 0`) may fall back to the existing authenticated `gh` session; permission failures, malformed state, and unrelated HTTP errors remain fail-closed.

## Exact monitored journeys

See [`CONTRACT.md`](CONTRACT.md). MatchMaker's launch check requires the exact no-follow redirect:

`https://matchmakerre.com/login` → HTTP 302 → `https://app.getjetai.com/launch/matchmaker`

A generic 2xx/3xx result is not sufficient.

## Incident response

### A system incident alert arrives

1. Read the named system, stage, and stable reason.
2. Open the status page and confirm whether state is fresh.
3. Inspect the latest Guardian workflow run and durable state.
4. Reprobe the exact failed public GET path read-only.
5. Classify current state as confirmed outage, transient recovery, authentication/entitlement failure, or monitor defect.
6. Do not restart any service without Renee's explicit approval in the moment.
7. Leave the incident state intact; Guardian will suppress duplicates and send recovery after the full journey passes.

### Heartbeat stale/unreadable alert arrives

1. Inspect whether the latest `Guardian Monitor` workflow is scheduled, queued, failed, or disabled.
2. Confirm GitHub Actions is enabled and the workflow still contains the five-minute offset schedule.
3. Inspect whether the heartbeat already attempted its one bounded workflow dispatch for that stale timestamp; manually dispatch only when it did not or when testing an approved code change.
4. Require a successful run, advancing `checked_at`, a fresh operational/degraded page, and one heartbeat recovery.
5. If a public-repository inactivity policy disabled schedules, re-enable the workflow; do not manufacture green state manually.

### Discord delivery fails

1. Treat the monitor run as failed and preserve stale-state escalation.
2. Verify bot/channel access without printing the token.
3. Read the token only through the approved vault cache (`Jet-Automations` → `Jet Discord` → `Key`).
4. Rotate the Discord token if exposure is suspected, update the encrypted GitHub secret, and verify a controlled non-incident message.

## Manual verification

```bash
gh workflow run "Guardian Monitor" --repo Eden-TDG/agent-tech-guardian --ref main
gh run list --repo Eden-TDG/agent-tech-guardian --workflow "Guardian Monitor" --limit 3
```

A successful verification requires:

- run conclusion `success`;
- all four systems represented;
- advancing `checked_at` in issue #1;
- status page freshness `fresh`;
- no incident for healthy systems;
- no output from a healthy heartbeat run.

## Local test and recovery

```bash
gh repo clone Eden-TDG/agent-tech-guardian
cd agent-tech-guardian
python3 -m pytest -q
python3 -m compileall -q agent_tech_guardian hermes tests
```

For a read-only live probe without Discord delivery:

```bash
TMPDIR=$(mktemp -d)
python3 -m agent_tech_guardian \
  --state-file "$TMPDIR/state.json" \
  --status-page "$TMPDIR/index.html" \
  --status-json "$TMPDIR/status.json"
```

No Discord token is required for a healthy local probe. Never place a production token in command history or repository files.

## Release procedure

1. Add a focused failing regression for changed behavior.
2. Implement the minimum correction.
3. Run the complete suite, compile check, workflow syntax check, `git diff --check`, current-tree secret scan, and full-history secret scan.
4. Push the exact tested commit.
5. Require CI and any page deployment to succeed at that SHA.
6. Manually dispatch Guardian and verify durable state advancement.
7. Verify the deployed page visually and through its live DOM.
8. Copy the tracked heartbeat script to `~/.hermes/scripts/`, require byte parity, and run its focused tests.
9. Inspect the persisted heartbeat cron: script, `no_agent: true`, five-minute schedule, delivery, and enabled state.
10. Run the cron no-LLM policy checker and one healthy silent execution.

## Known boundary

V1 validates public/pre-authenticated launch contracts. It does not claim authenticated role visibility or Chat AI answer quality. Those require a minimally entitled synthetic identity with an approved credential lifecycle and zero-write constraints; no permanent login bypass is permitted.
