from pathlib import Path
import re


WORKFLOWS = Path(".github/workflows")


def test_all_github_actions_are_pinned_to_full_commit_shas():
    uses = []
    for path in WORKFLOWS.glob("*.yml"):
        uses.extend(re.findall(r"uses:\s*([^\s]+)", path.read_text()))
    assert uses
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", item) for item in uses), uses


def test_ci_compiles_every_shipped_python_tree():
    ci = (WORKFLOWS / "ci.yml").read_text()
    assert "compileall -q agent_tech_guardian hermes tests" in ci


def test_monitor_workflow_has_minimum_explicit_permissions():
    monitor = (WORKFLOWS / "monitor.yml").read_text()
    permissions = monitor.split("permissions:", 1)[1].split("env:", 1)[0]
    assert "contents: read" in permissions
    assert "issues: write" in permissions
    assert "actions: write" not in permissions
    assert "contents: write" not in permissions