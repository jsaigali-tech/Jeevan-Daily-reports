#!/usr/bin/env python3
"""
APEX Daily Sprint Report — Queries Jira (AINV, ARPT, AEM) and posts to Slack.
Runs via GitHub Actions at 6 AM PST Mon–Fri (even when your Mac is off).
"""
import os
import sys
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

JIRA_BASE = "https://axsteam.atlassian.net"
JEEVAN_ACCOUNT_ID = "712020:e120aabc-952c-4382-a09a-4dda72fef47c"


def jira_request(jql: str, fields: list[str]) -> list[dict]:
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not email or not token:
        print("ERROR: Set JIRA_EMAIL and JIRA_API_TOKEN", file=sys.stderr)
        sys.exit(1)
    fields_str = ",".join(fields)
    url = f"{JIRA_BASE}/rest/api/3/search/jql?jql={urllib.parse.quote(jql)}&maxResults=50&fields={urllib.parse.quote(fields_str)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
            return data.get("issues", [])
    except urllib.error.HTTPError as e:
        print(f"Jira API error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def slack_post(text: str) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL") or "D0AMF37Q7JS"
    if not token:
        print("ERROR: Set SLACK_BOT_TOKEN", file=sys.stderr)
        sys.exit(1)
    today = datetime.now().strftime("%A, %b %d %Y")
    payload = {
        "channel": channel,
        "text": f"📋 APEX Daily Sprint Report — {today}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"📋 APEX Daily Sprint Report — {today}", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        ],
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=data,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read().decode())
            if not resp.get("ok"):
                print(f"Slack API error: {resp.get('error', 'unknown')}", file=sys.stderr)
                sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"Slack API error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def fmt_link(key: str, text: str) -> str:
    return f"<https://axsteam.atlassian.net/browse/{key}|{text}>"


def fmt_assignee(issue: dict) -> str:
    a = issue.get("fields", {}).get("assignee")
    return a.get("displayName", "⚠️ Unassigned") if a else "⚠️ Unassigned"


def fmt_priority_emoji(name: str) -> str:
    m = {"Critical": "🔴", "Highest": "🔴", "High": "🟠", "Medium": "🟡", "Low": "⚪", "Lowest": "⚪"}
    return m.get(name, "⚪")


def main() -> None:
    my_items = jira_request(
        f'project in (AINV, ARPT, AEM) AND assignee = "{JEEVAN_ACCOUNT_ID}" AND statusCategory != Done ORDER BY priority DESC, updated DESC',
        ["summary", "status", "issuetype", "priority", "updated", "project"],
    )
    bugs_ainv_arpt = jira_request(
        "project in (AINV, ARPT) AND issuetype = Bug AND statusCategory != Done ORDER BY priority DESC, updated DESC",
        ["summary", "status", "priority", "assignee", "project"],
    )
    new_stories = jira_request(
        "project in (AINV, ARPT) AND issuetype = Story AND created >= -14d ORDER BY created DESC",
        ["summary", "status", "priority", "assignee", "created", "project"],
    )
    prerelease = jira_request(
        "project in (AINV, ARPT) AND issuetype = Bug AND statusCategory != Done AND fixVersion in unreleasedVersions() ORDER BY priority DESC",
        ["summary", "status", "priority", "assignee", "fixVersions"],
    )
    aem_bugs = jira_request(
        "project = AEM AND issuetype = Bug AND statusCategory != Done ORDER BY priority DESC, updated DESC",
        ["summary", "status", "priority", "assignee"],
    )
    ainv_bugs = [i for i in bugs_ainv_arpt if i["fields"]["project"]["key"] == "AINV"]
    arpt_bugs = [i for i in bugs_ainv_arpt if i["fields"]["project"]["key"] == "ARPT"]

    lines = []
    lines.append("*👤 YOUR ITEMS (" + str(len(my_items)) + " open)*")
    lines.append("──────────────────────────")
    for i in my_items:
        f = i["fields"]
        key = i["key"]
        proj = f["project"]["key"]
        emoji = fmt_priority_emoji(f["priority"]["name"])
        status = f["status"]["name"]
        updated = f.get("updated", "")[:10] if f.get("updated") else ""
        lines.append(f"{emoji} *{fmt_link(key, key)}* — {f['summary']}")
        lines.append(f"   Project: {proj} | Status: {status} | Updated: {updated}")
        lines.append("   ⚡ Follow up with reviewer — check comments, close if clear.")
        lines.append("")
    if not my_items:
        lines.append("_No open items assigned to you._")
        lines.append("")

    lines.append("*🐛 BUGS TO WATCH*")
    lines.append("──────────────────────────")
    lines.append(f"*AINV:* {len(ainv_bugs)} open  |  *ARPT:* {len(arpt_bugs)} open  |  *AEM:* {len(aem_bugs)} open  =  *{len(bugs_ainv_arpt) + len(aem_bugs)} total*")
    lines.append("")
    critical = [i for i in bugs_ainv_arpt if i["fields"]["priority"]["name"] == "Critical"][:5]
    for i in critical:
        key = i["key"]
        assignee = fmt_assignee(i)
        s = i["fields"]["summary"]
        lines.append(f"🔴 {fmt_link(key, key)} {assignee} — {(s[:57] + '...') if len(s) > 60 else s}")
    for i in prerelease[:3]:
        key = i["key"]
        fv = ((i["fields"].get("fixVersions") or [{}])[0].get("name", "")) or "unreleased"
        s = i["fields"]["summary"]
        lines.append(f"🟠 *RELEASE BLOCKER:* {fmt_link(key, key)} — {(s[:47] + '...') if len(s) > 50 else s} (blocking {fv})")
    lines.append("")
    lines.append("<https://axsteam.atlassian.net/issues/?jql=project+in+(AINV,ARPT,AEM)+AND+issuetype=Bug+AND+statusCategory+!=+Done+ORDER+BY+priority+DESC|→ View all open bugs>")
    lines.append("")

    lines.append("*✨ NEW STORIES (last 14 days)*")
    lines.append("──────────────────────────")
    for i in new_stories[:5]:
        key = i["key"]
        assignee = fmt_assignee(i)
        created = (i["fields"].get("created") or "")[:10]
        lines.append(f"🟠 {fmt_link(key, key)} — {i['fields']['summary'][:50]}... | {assignee} | {created}")
    lines.append("")

    lines.append("*🚦 RELEASE READINESS*")
    lines.append("──────────────────────────")
    if prerelease:
        lines.append(f"❌ ARPT/AINV — {len(prerelease)} open bug(s) targeting unreleased version")
        for i in prerelease[:3]:
            lines.append(f"   • {fmt_link(i['key'], i['key'])} — {i['fields']['summary'][:50]}...")
    else:
        lines.append("✅ No open bugs targeting unreleased version")
    lines.append("✅ Your items — Not blocked" if my_items else "✅ No items assigned")
    lines.append("")
    lines.append("*Overall: 🟡 AT RISK*" if prerelease else "*Overall: 🟢 READY*")
    lines.append("")

    lines.append("*📌 TOP 3 ACTIONS TODAY*")
    lines.append("──────────────────────────")
    actions = []
    for i in my_items:
        actions.append(f"1. {fmt_link(i['key'], i['key'])} — Check review comments and close/update.")
    if prerelease and len(actions) < 3:
        actions.append(f"{len(actions)+1}. {fmt_link(prerelease[0]['key'], prerelease[0]['key'])} — Release blocker. Confirm assignee is on it.")
    while len(actions) < 3:
        actions.append(f"{len(actions)+1}. Review open bugs and assign unassigned Critical.")
    lines.extend(actions[:3])
    lines.append("")
    lines.append("*📎 Quick links:* <https://axsteam.atlassian.net/jira/software/projects/AINV/boards|AINV> | <https://axsteam.atlassian.net/jira/software/projects/ARPT/boards|ARPT> | <https://axsteam.atlassian.net/jira/software/projects/AEM/boards|AEM>")

    report = "\n".join(lines)
    slack_post(report)
    print("✅ Daily sprint report posted to Slack.")


if __name__ == "__main__":
    main()
