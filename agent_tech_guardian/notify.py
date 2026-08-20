from __future__ import annotations

import json
import urllib.request
from typing import Any


class NullNotifier:
    def send(self, event: dict[str, Any]) -> None:
        return None


class DiscordNotifier:
    def __init__(self, token: str, channel_id: str, *, status_url: str = "") -> None:
        self.token = token
        self.channel_id = channel_id
        self.status_url = status_url

    def send(self, event: dict[str, Any]) -> None:
        if event["type"] == "alert":
            content = (
                f"🔴 **Agent Technology Incident — {event['display_name']}**\n"
                f"Failed stage: `{event['stage']}`\n"
                f"Reason: `{event['reason']}`\n"
                f"Confirmed on two consecutive checks. Agent impact: {event['display_name']} may be unavailable."
            )
        else:
            content = (
                f"✅ **Agent Technology Recovered — {event['display_name']}**\n"
                "The complete monitored journey is passing again."
            )
        if self.status_url:
            content += f"\nStatus: {self.status_url}"
        payload = json.dumps({"content": content}).encode("utf-8")
        request = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{self.channel_id}/messages",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bot {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "Agent-Tech-Guardian/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f"discord_http_{response.status}")
