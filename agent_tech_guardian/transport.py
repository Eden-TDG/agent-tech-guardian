from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Response:
    status: int
    body: str
    headers: dict[str, str]

    def json(self) -> Any:
        return json.loads(self.body)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UrllibTransport:
    def __init__(self, *, timeout: float = 15.0, user_agent: str = "Agent-Tech-Guardian/1.0") -> None:
        self.timeout = timeout
        self.user_agent = user_agent

    def get(self, url: str, *, follow_redirects: bool = True) -> Response:
        opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(_NoRedirect())
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent}, method="GET")
        try:
            with opener.open(request, timeout=self.timeout) as response:
                body = response.read(2_500_000).decode("utf-8", "replace")
                return Response(response.status, body, dict(response.headers.items()))
        except urllib.error.HTTPError as exc:
            body = exc.read(250_000).decode("utf-8", "replace")
            return Response(exc.code, body, dict(exc.headers.items()))
