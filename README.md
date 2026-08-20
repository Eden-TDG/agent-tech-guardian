# Agent Tech Guardian

Independent synthetic availability monitoring for TDG's agent-facing technology.

Guardian runs outside the monitored applications and validates real public launch and UI contracts—not only process uptime. It is deterministic, read-only, and alert-only.

## V1 coverage

- JetAI health and sign-in surface
- MatchMaker health and JetAI entitlement handoff
- Jet Center health and sign-in surface
- Renee TO-DO UI and data API

## Incident behavior

- One bounded retry for transient failures
- Two matching failed runs before paging
- One alert per stable incident
- One recovery message after a previously alerted incident
- Sanitized public status output
- No automatic restarts or production writes

See [`docs/CONTRACT.md`](docs/CONTRACT.md) for the exact acceptance contract.

## Status

The production status page is published by the scheduled Guardian workflow after deployment.
