"""Status-page rendering contract."""

from __future__ import annotations

import pytest

from conftest import prospective


def render(value):
    renderer = prospective("agent_tech_guardian.render", "render_status_page")
    return renderer(value)


def report(overall="operational"):
    return {
        "overall": overall,
        "checked_at": "2026-08-20T12:00:00Z",
        "systems": {
            "jetai": {
                "display_name": "JetAI",
                "state": "operational",
                "stage": None,
                "reason": None,
                "diagnostic": "",
                "last_successful_journey": "2026-08-20T12:00:00Z",
            },
            "matchmaker": {
                "display_name": "MatchMaker",
                "state": "outage" if overall != "operational" else "operational",
                "stage": "login" if overall != "operational" else None,
                "reason": "unexpected_redirect" if overall != "operational" else None,
                "diagnostic": "redirect contract mismatch" if overall != "operational" else "",
                "last_successful_journey": "2026-08-20T11:55:00Z",
            },
        },
    }


@pytest.mark.parametrize("overall", ["operational", "degraded", "outage"])
def test_page_renders_overall_state(overall):
    html = render(report(overall))
    assert f'data-overall="{overall}"' in html
    assert overall.title() in html


def test_page_renders_each_system_last_check_and_last_success():
    html = render(report("degraded"))
    assert "JetAI" in html
    assert "MatchMaker" in html
    assert "2026-08-20T12:00:00Z" in html
    assert "2026-08-20T11:55:00Z" in html
    assert "Last checked" in html
    assert "Last successful journey" in html
    assert 'data-system-state="outage"' in html


def test_page_escapes_diagnostics():
    value = report("degraded")
    value["systems"]["matchmaker"]["diagnostic"] = '<script>alert("secret")</script>'
    html = render(value)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
