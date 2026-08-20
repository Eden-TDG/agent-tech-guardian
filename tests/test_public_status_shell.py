from pathlib import Path


def test_public_status_shell_reads_sanitized_guardian_state_without_html_injection():
    page = Path("public/index.html")
    assert page.exists(), "RED: public status shell is missing"
    html = page.read_text()
    assert "api.github.com/repos/Eden-TDG/agent-tech-guardian/issues/1" in html
    assert "setInterval(loadStatus" in html
    assert ".textContent" in html
    assert "innerHTML" not in html
