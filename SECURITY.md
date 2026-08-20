# Security Policy

## Reporting a vulnerability

Do not place credentials, tokens, cookies, private endpoint details, or customer data in a public issue.

Use GitHub's **Report a vulnerability** private reporting flow for this repository. Operational incidents should be reported privately to the TDG automation owner.

## Security boundaries

Agent Tech Guardian is intentionally:

- read-only against monitored applications;
- credential-free for application probes;
- alert-only, with no service restart or self-healing authority;
- limited to sanitized system names, state, timestamps, stage, and stable reason codes in public output;
- protected by encrypted GitHub Actions secrets for Discord delivery;
- backed by a deterministic zero-LLM heartbeat watchdog.

A leaked Discord bot token, GitHub credential, or future synthetic-agent credential must be treated as compromised and rotated before the workflow is called fully recovered. Removing a value from current source is not sufficient when it appeared in public Git history.

## Supported version

The latest release on the default branch is supported.
