from __future__ import annotations

from html import escape


LABELS = {"operational": "Operational", "degraded": "Degraded", "outage": "Outage"}


def render_status_page(report: dict) -> str:
    overall = report.get("overall", "degraded")
    checked = escape(str(report.get("checked_at", "unknown")))
    cards = []
    for key, system in report.get("systems", {}).items():
        state = escape(str(system.get("state", "outage")))
        name = escape(str(system.get("display_name", key)))
        success = escape(str(system.get("last_successful_journey") or "Not yet observed"))
        stage = escape(str(system.get("stage") or ""))
        reason = escape(str(system.get("reason") or ""))
        diagnostic = escape(str(system.get("diagnostic") or ""))
        detail = ""
        if stage or reason:
            detail = f'<p class="reason">{stage}: {reason}</p><p class="diag">{diagnostic}</p>'
        cards.append(
            f'<article class="card {state}" data-system-state="{state}">'
            f'<div class="card-head"><h2>{name}</h2><span>{LABELS.get(state, state.title())}</span></div>'
            f'{detail}<p><strong>Last successful journey</strong><br>{success}</p></article>'
        )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60"><title>Agent Technology Status</title>
<style>
:root{{--navy:#07182b;--panel:#10263f;--text:#f5f8fc;--muted:#a9b8c9;--green:#20c997;--yellow:#ffca2c;--red:#ff5b68}}
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(145deg,#061321,#102845);color:var(--text);font:16px system-ui,-apple-system,Segoe UI,sans-serif;min-height:100vh}}
main{{max-width:1040px;margin:auto;padding:42px 20px}}header{{margin-bottom:28px}}h1{{font-size:clamp(30px,6vw,54px);margin:.15em 0}}.eyebrow,.updated{{color:var(--muted);letter-spacing:.08em;text-transform:uppercase;font-size:13px}}.overall{{display:inline-block;padding:9px 14px;border-radius:999px;font-weight:800;background:#183954}}[data-overall="operational"] .overall{{color:var(--green)}}[data-overall="degraded"] .overall{{color:var(--yellow)}}[data-overall="outage"] .overall{{color:var(--red)}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}.card{{background:rgba(16,38,63,.94);border:1px solid #294864;border-left:5px solid var(--green);border-radius:16px;padding:20px;box-shadow:0 12px 28px #0004}}.card.outage{{border-left-color:var(--red)}}.card-head{{display:flex;justify-content:space-between;gap:12px;align-items:center}}h2{{margin:0;font-size:21px}}.card-head span{{font-size:12px;text-transform:uppercase;font-weight:800;color:var(--green)}}.card.outage .card-head span{{color:var(--red)}}p{{color:var(--muted);line-height:1.5}}.reason{{color:#ffd2d6;font-weight:700}}.diag{{font-size:13px}}footer{{margin-top:28px;color:var(--muted);font-size:13px}}
</style></head><body data-overall="{escape(overall)}"><main><header><div class="eyebrow">Agent Tech Guardian</div><h1>Technology Status</h1><div class="overall">{LABELS.get(overall, overall.title())}</div><p class="updated">Last checked {checked}</p></header><section class="grid">{''.join(cards)}</section><footer>Read-only synthetic monitoring · No automatic restarts · Refreshes every 60 seconds</footer></main></body></html>'''
