#!/usr/bin/env python3
"""
AINV QA Tomorrow — Apex Inventory QA task plan for the next workday.
Fetches AINV-only Jira data, prioritizes items in QA / assigned to Jeevan,
and posts an AI-generated execution plan to Slack (or stdout).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

_MODULE_PATH = Path(__file__).parent / "daily-sprint-report.py"
_spec = importlib.util.spec_from_file_location("daily_sprint_report", _MODULE_PATH)
if _spec is None or _spec.loader is None:
    print(f"ERROR: Cannot load {_MODULE_PATH}", file=sys.stderr)
    sys.exit(1)
dsp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dsp)

PROJECT = "AINV"
QA_STATUSES = ('"In QA"', '"QA"', '"Deployed to QA"', '"Ready for QA"', '"Testing"', '"QA In Progress"')
READY_STATUSES = (
    '"Ready for Production"',
    '"Ready for Prod"',
    '"Ready for Release"',
    '"Ready for Release to Production"',
)


def _tomorrow_label() -> tuple[str, str]:
    tomorrow = datetime.now() + timedelta(days=1)
    return tomorrow.strftime("%A, %b %d %Y"), tomorrow.strftime("%Y-%m-%d")


def _plain_link(key: str) -> str:
    return f"https://axsteam.atlassian.net/browse/{key}"


def _fallback_ainv_report(
    my_items,
    deployed_to_qa,
    ready_for_prod,
    blocked_issues,
    ainv_bugs,
    prerelease,
    due_tomorrow,
    tomorrow_label: str,
) -> str:
    lines = [f"*AINV QA PLAN — {tomorrow_label}*", ""]

    if deployed_to_qa:
        lines.append(f"*TEST EXECUTION ({len(deployed_to_qa)} in QA)*")
        for issue in deployed_to_qa[:10]:
            key = issue["key"]
            fields = issue["fields"]
            lines.append(
                f"• <{_plain_link(key)}|{key}> — {fields.get('summary', '')[:55]} | {fields.get('status', {}).get('name', '')}"
            )
        lines.append("")

    if due_tomorrow:
        lines.append(f"*DUE TOMORROW ({len(due_tomorrow)})*")
        for issue in due_tomorrow[:8]:
            key = issue["key"]
            fields = issue["fields"]
            lines.append(
                f"• <{_plain_link(key)}|{key}> — {fields.get('summary', '')[:55]} | {fields.get('status', {}).get('name', '')}"
            )
        lines.append("")

    lines.append(f"*YOUR AINV ITEMS ({len(my_items)} open)*")
    for issue in my_items[:12]:
        key = issue["key"]
        fields = issue["fields"]
        lines.append(
            f"• <{_plain_link(key)}|{key}> — {fields.get('summary', '')[:55]} | {fields.get('status', {}).get('name', '')}"
        )
    if not my_items:
        lines.append("_No open AINV items assigned to you._")
    lines.append("")

    if ready_for_prod:
        lines.append(f"*READY FOR PRODUCTION ({len(ready_for_prod)})*")
        for issue in ready_for_prod[:5]:
            key = issue["key"]
            lines.append(f"• <{_plain_link(key)}|{key}> — {issue['fields'].get('summary', '')[:55]}")
        lines.append("")

    if blocked_issues:
        lines.append(f"*BLOCKERS ({len(blocked_issues)})*")
        for issue in blocked_issues[:5]:
            key = issue["key"]
            lines.append(f"• <{_plain_link(key)}|{key}> — {issue['fields'].get('summary', '')[:55]}")
        lines.append("")

    lines.append(f"*BUGS TO WATCH — {len(ainv_bugs)} open AINV bugs*")
    for issue in prerelease[:3]:
        key = issue["key"]
        lines.append(f"🟠 <{_plain_link(key)}|{key}> — {issue['fields'].get('summary', '')[:50]}")
    lines.append("")

    lines.append("*TOP 5 ACTIONS FOR TOMORROW*")
    action_pool = deployed_to_qa + due_tomorrow + my_items
    actions = []
    for idx, issue in enumerate(action_pool[:5], start=1):
        key = issue["key"]
        actions.append(
            f"{idx}. Execute QA on <{_plain_link(key)}|{key}> — review comments, run regression, log results."
        )
    next_idx = len(actions) + 1
    while len(actions) < 5:
        actions.append(f"{next_idx}. Triage open AINV bugs and unblock QA pipeline.")
        next_idx += 1
    lines.extend(actions)

    lines.append("")
    lines.append("*RESOURCES:*")
    lines.append(f"<https://axsteam.atlassian.net/jira/software/projects/AINV/boards|AINV Board>")
    lines.append(
        "<https://axsteam.atlassian.net/issues/?jql=project+%3D+AINV+AND+statusCategory+%21%3D+Done|All open AINV>"
    )
    return "\n".join(lines)


def _deliver(report: str, tomorrow_label: str) -> None:
    if os.environ.get("OUTPUT_MODE", "").lower() == "stdout":
        print(report)
        print(f"\n✅ AINV QA plan generated for {tomorrow_label}.")
        return

    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print(report)
        print(f"\n✅ AINV QA plan generated for {tomorrow_label} (stdout — no SLACK_BOT_TOKEN).")
        return

    today_header = f"📦 AINV QA Tomorrow — {tomorrow_label}"
    chunk_size = 2990
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": today_header, "emoji": True}}]
    for i in range(0, len(report), chunk_size):
        chunk = report[i : i + chunk_size]
        if chunk.strip():
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})

    import json
    import urllib.request

    payload = {"channel": os.environ.get("SLACK_CHANNEL") or "D0AMF37Q7JS", "text": today_header, "blocks": blocks}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=data,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        body = json.loads(response.read().decode())
        if not body.get("ok"):
            print(f"Slack API error: {body.get('error', 'unknown')}", file=sys.stderr)
            sys.exit(1)
    print(f"✅ AINV QA plan posted to Slack for {tomorrow_label}.")


def main() -> None:
    tomorrow_label, tomorrow_iso = _tomorrow_label()
    print(f"Fetching AINV QA data for {tomorrow_label}...")

    base_fields = [
        "summary",
        "status",
        "issuetype",
        "priority",
        "updated",
        "project",
        "assignee",
        "created",
        "duedate",
        "fixVersions",
    ]
    qa_status_jql = ", ".join(QA_STATUSES)
    ready_status_jql = ", ".join(READY_STATUSES)

    my_items = dsp.jira_request(
        f'project = {PROJECT} AND assignee = "{dsp.JEEVAN_ACCOUNT_ID}" AND statusCategory != Done ORDER BY priority DESC, updated DESC',
        base_fields,
    )
    deployed_to_qa = dsp._safe_jira_request(
        f"project = {PROJECT} AND status in ({qa_status_jql}) ORDER BY priority DESC, updated DESC",
        base_fields,
    )
    ready_for_prod = dsp._safe_jira_request(
        f"project = {PROJECT} AND status in ({ready_status_jql}) ORDER BY priority DESC, updated DESC",
        base_fields,
    )
    blocked_issues = dsp._safe_jira_request(
        f"project = {PROJECT} AND status = Blocked ORDER BY priority DESC, updated DESC",
        base_fields,
    )
    ainv_bugs = dsp.jira_request(
        f"project = {PROJECT} AND issuetype = Bug AND statusCategory != Done ORDER BY priority DESC, updated DESC",
        ["summary", "status", "priority", "assignee", "updated", "fixVersions"],
    )
    prerelease = dsp.jira_request(
        f"project = {PROJECT} AND issuetype = Bug AND statusCategory != Done AND fixVersion in unreleasedVersions() ORDER BY priority DESC",
        ["summary", "status", "priority", "assignee", "fixVersions", "updated"],
    )
    due_tomorrow = dsp._safe_jira_request(
        f'project = {PROJECT} AND duedate = "{tomorrow_iso}" AND statusCategory != Done ORDER BY priority DESC',
        base_fields,
    )
    recent_changes = dsp.jira_request(
        f"project = {PROJECT} AND updated >= -7d ORDER BY updated DESC",
        base_fields,
    )

    my_items_detail = [dsp.fmt_issue(issue, include_comments=True) for issue in my_items]
    deployed_detail = [dsp.fmt_issue(issue, include_comments=True) for issue in deployed_to_qa[:15]]
    critical_bugs = [issue for issue in ainv_bugs if issue["fields"].get("priority", {}).get("name") == "Critical"]
    critical_detail = [dsp.fmt_issue(issue, include_comments=True) for issue in critical_bugs[:5]]

    context = f"""
TARGET DAY: {tomorrow_label} ({tomorrow_iso})
PROJECT: AINV (Apex Inventory) only

=== YOUR AINV ITEMS (assigned to Jeevan, not Done) ===
{chr(10).join(my_items_detail) if my_items_detail else "None"}

=== AINV DEPLOYED TO QA (execute tests tomorrow) ===
{chr(10).join(deployed_detail) if deployed_detail else "None"}

=== AINV DUE TOMORROW ===
{chr(10).join(dsp.fmt_issue(issue) for issue in due_tomorrow) if due_tomorrow else "None"}

=== AINV READY FOR PRODUCTION ===
{chr(10).join(dsp.fmt_issue(issue) for issue in ready_for_prod[:10]) if ready_for_prod else "None"}

=== AINV BLOCKED ===
{chr(10).join(dsp.fmt_issue(issue) for issue in blocked_issues[:10]) if blocked_issues else "None"}

=== AINV CRITICAL BUGS ===
{chr(10).join(critical_detail) if critical_detail else "None"}

=== AINV RELEASE BLOCKERS ===
{chr(10).join(dsp.fmt_issue(issue) for issue in prerelease[:8]) if prerelease else "None"}

=== AINV RECENT CHANGES (7d) ===
{chr(10).join(dsp.fmt_issue(issue) for issue in recent_changes[:12]) if recent_changes else "None"}

=== COUNTS ===
Open AINV bugs: {len(ainv_bugs)} | In QA: {len(deployed_to_qa)} | Your items: {len(my_items)} | Due tomorrow: {len(due_tomorrow)}

=== LINKS ===
AINV board: https://axsteam.atlassian.net/jira/software/projects/AINV/boards
My AINV items: https://axsteam.atlassian.net/issues/?jql=project+%3D+AINV+AND+assignee+%3D+currentUser()+AND+statusCategory+%21%3D+Done
"""

    system_prompt = f"""You are the APEX Inventory (AINV) QA Lead assistant for Jeevan.
Produce a focused QA EXECUTION PLAN for *tomorrow* ({tomorrow_label}).

Every ticket mention MUST use Slack link format: <https://axsteam.atlassian.net/browse/KEY|KEY>

OUTPUT (Slack mrkdwn):
- *QUICK SNAPSHOT* — 2-3 bullets for tomorrow's AINV QA focus
- *PRIORITY TEST QUEUE* — Ordered list of tickets to test tomorrow (In QA first, then due tomorrow, then your assigned items). Per ticket: status, what changed (from comments), suggested test cases (3-5 incl. edge/negative), expected outcome, link.
- *BLOCKERS & RISKS* — Anything stopping QA tomorrow
- *READY FOR PROD SIGN-OFF* — Items that may be signed off after tomorrow's testing
- *TOP 5 ACTIONS FOR TOMORROW* — Concrete, time-ordered steps with ticket links
- *RESOURCES* — AINV board and filtered JQL links

Be specific and actionable. This is for hands-on QA execution, not a generic status update."""

    print("Generating AI plan...")
    report = dsp.ai_analyze(context, system_prompt)
    if not report:
        print("No AI key available. Using structured fallback.", file=sys.stderr)
        report = _fallback_ainv_report(
            my_items,
            deployed_to_qa,
            ready_for_prod,
            blocked_issues,
            ainv_bugs,
            prerelease,
            due_tomorrow,
            tomorrow_label,
        )

    _deliver(report, tomorrow_label)


if __name__ == "__main__":
    main()
