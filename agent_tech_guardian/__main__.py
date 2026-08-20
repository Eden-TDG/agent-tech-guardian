from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .monitor import Monitor, SystemClock
from .notify import DiscordNotifier, NullNotifier
from .render import render_status_page
from .storage import JsonStateStore
from .transport import UrllibTransport

STATUS_URL = "https://eden-tdg.github.io/agent-tech-guardian/"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent Tech Guardian — deterministic agent-facing availability monitor")
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--status-page", required=True)
    parser.add_argument("--status-json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    channel = os.environ.get("DISCORD_CHANNEL_ID", "")
    notifier = DiscordNotifier(token, channel, status_url=STATUS_URL) if token and channel else NullNotifier()
    monitor = Monitor(
        transport=UrllibTransport(),
        clock=SystemClock(),
        state_store=JsonStateStore(args.state_file),
        notifier=notifier,
    )
    report = monitor.run()
    page = Path(args.status_page)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(render_status_page(report))
    status_json = Path(args.status_json) if args.status_json else page.with_name("status.json")
    status_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"overall": report["overall"], "checked_at": report["checked_at"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
