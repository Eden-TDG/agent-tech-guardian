from pathlib import Path


def test_public_status_shell_reads_sanitized_guardian_state_without_html_injection():
    page = Path("public/index.html")
    assert page.exists(), "RED: public status shell is missing"
    html = page.read_text()
    assert "api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/1" in html
    assert "setInterval(loadStatus" in html
    assert ".textContent" in html
    assert "innerHTML" not in html


def test_public_status_shell_fails_visibly_closed_when_monitor_state_is_stale():
    html = Path("public/index.html").read_text()
    assert "STALE_AFTER_MS" in html
    assert "Date.now()" in html
    assert "Status Unavailable" in html
    assert "data.freshness" in html
    assert "Monitor data is stale" in html
    assert "unreadable" in html
    assert "Status data is temporarily unavailable" in html
