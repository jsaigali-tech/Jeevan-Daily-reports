#!/usr/bin/env python3
"""
StandupPulse — AI-powered analysis of Jira + Confluence.
Fetches Jira issues, comments, Confluence content; uses AI to analyze priorities,
deadlines, risk, and generate actionable insights. Posts to Slack.
Runs via GitHub Actions at 6 AM PST Mon–Fri.
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
CONFLUENCE_BASE = "https://axsteam.atlassian.net/wiki"
JEEVAN_ACCOUNT_ID = "712020:e120aabc-952c-4382-a09a-4dda72fef47c"


def _auth_headers() -> dict:
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not email or not token:
        print("ERROR: Set JIRA_EMAIL and JIRA_API_TOKEN", file=sys.stderr)
        sys.exit(1)
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {"Accept": "application/json", "Authorization": f"Basic {auth}"}


def _get(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _post(url: str, headers: dict, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def jira_request(jql: str, fields: list[str]) -> list[dict]:
    """Use POST /rest/api/3/search/jql (legacy /search was removed, returns 410)."""
    url = f"{JIRA_BASE}/rest/api/3/search/jql"
    headers = {**_auth_headers(), "Content-Type": "application/json"}
    body = {"jql": jql, "maxResults": 50, "fields": fields}
    try:
        data = _post(url, headers, body)
        return data.get("issues", [])
    except urllib.error.HTTPError as e:
        print(f"Jira API error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def _safe_jira_request(jql: str, fields: list[str]) -> list[dict]:
    """Like jira_request but returns [] on error (for optional queries like Blocked)."""
    url = f"{JIRA_BASE}/rest/api/3/search/jql"
    headers = {**_auth_headers(), "Content-Type": "application/json"}
    body = {"jql": jql, "maxResults": 50, "fields": fields}
    try:
        data = _post(url, headers, body)
        return data.get("issues", [])
    except urllib.error.HTTPError:
        return []


def jira_get_comments(issue_key: str) -> list[dict]:
    url = f"{JIRA_BASE}/rest/api/3/issue/{issue_key}/comment"
    try:
        data = _get(url, _auth_headers())
        comments = data.get("comments", [])
        return [
            {
                "author": c.get("author", {}).get("displayName", "Unknown"),
                "body": _strip_html(c.get("body", {}).get("content", [])),
                "created": c.get("created", "")[:10],
            }
            for c in comments[-15:]  # last 15 comments
        ]
    except urllib.error.HTTPError:
        return []


def _strip_html(adf_content: list) -> str:
    """Extract plain text from Atlassian Document Format."""
    if not isinstance(adf_content, list):
        return ""
    text_parts = []
    for node in adf_content:
        if isinstance(node, dict):
            if node.get("type") == "text":
                text_parts.append(node.get("text", ""))
            elif "content" in node:
                text_parts.append(_strip_html(node["content"]))
    return " ".join(text_parts).strip()[:500]  # limit length


def confluence_search(cql: str, limit: int = 5) -> list[dict]:
    url = f"{CONFLUENCE_BASE}/rest/api/search?cql={urllib.parse.quote(cql)}&limit={limit}"
    try:
        data = _get(url, _auth_headers())
        results = data.get("results", [])
        out = []
        for r in results:
            content = r.get("content", r)
            title = content.get("title", r.get("title", ""))
            excerpt = (r.get("excerpt") or "").replace("<highlight>", "").replace("</highlight>", "")[:300]
            links = content.get("_links", {})
            webui = links.get("webui", links.get("webui", ""))
            url_str = f"https://axsteam.atlassian.net{webui}" if webui.startswith("/") else webui
            out.append({"title": title, "excerpt": excerpt, "url": url_str or ""})
        return out
    except (urllib.error.HTTPError, KeyError) as e:
        print(f"Confluence search skipped: {e}", file=sys.stderr)
        return []


def _ai_request(url: str, headers: dict, payload: dict) -> str:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.loads(r.read().decode())
    return resp


def _gemini_analyze(context: str, system_prompt: str) -> str:
    """Use Google Gemini (free tier) — get key at aistudio.google.com"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return ""
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": context}]}],
        "generationConfig": {"maxOutputTokens": 4000, "temperature": 0.3},
    }
    try:
        resp = _ai_request(url, {"Content-Type": "application/json"}, payload)
        text = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return text.strip()
    except (urllib.error.HTTPError, KeyError, IndexError) as e:
        print(f"Gemini API error: {e}", file=sys.stderr)
        return ""


def _openai_analyze(context: str, system_prompt: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ],
        "max_tokens": 4000,
        "temperature": 0.3,
    }
    try:
        resp = _ai_request(url, {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, payload)
        return resp["choices"][0]["message"]["content"].strip()
    except (urllib.error.HTTPError, KeyError) as e:
        print(f"OpenAI API error: {e}", file=sys.stderr)
        return ""


def ai_analyze(context: str, system_prompt: str) -> str:
    """Try Gemini first (free), then OpenAI. Returns empty if neither available."""
    report = _gemini_analyze(context, system_prompt)
    if report:
        return report
    report = _openai_analyze(context, system_prompt)
    if report:
        return report
    return ""


def slack_post(text: str) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL") or "D0AMF37Q7JS"
    if not token:
        print("ERROR: Set SLACK_BOT_TOKEN", file=sys.stderr)
        sys.exit(1)
    today = datetime.now().strftime("%A, %b %d %Y")
    payload = {
        "channel": channel,
        "text": f"📋 StandupPulse — {today}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"📋 StandupPulse — {today}", "emoji": True}},
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


def _fmt_link(key: str, text: str) -> str:
    return f"<https://axsteam.atlassian.net/browse/{key}|{text}>"


def _fallback_report(my_items, bugs_ainv_arpt, new_stories, prerelease, aem_bugs, blocked_issues=None, recent_changes=None) -> str:
    """Basic report when no AI key is available."""
    blocked_issues = blocked_issues or []
    recent_changes = recent_changes or []
    lines = []
    ainv_bugs = [i for i in bugs_ainv_arpt if i["fields"]["project"]["key"] == "AINV"]
    arpt_bugs = [i for i in bugs_ainv_arpt if i["fields"]["project"]["key"] == "ARPT"]

    if blocked_issues:
        lines.append("*BLOCKERS (" + str(len(blocked_issues)) + ")*")
        for i in blocked_issues[:5]:
            lines.append(f"• {_fmt_link(i['key'], i['key'])} — {i['fields'].get('summary', '')[:50]} | {i['fields'].get('status', {}).get('name', '')}")
        lines.append("")
    lines.append("*YOUR ITEMS (" + str(len(my_items)) + " open)*")
    lines.append("──────────────────────────")
    for i in my_items:
        f = i["fields"]
        key = i["key"]
        status = f.get("status", {}).get("name", "")
        updated = (f.get("updated") or "")[:10]
        lines.append(f"• {_fmt_link(key, key)} — {f.get('summary', '')[:60]} | {status} | Updated: {updated}")
    if not my_items:
        lines.append("_No open items assigned to you._")
    lines.append("")

    lines.append("*🐛 BUGS TO WATCH*")
    lines.append(f"*AINV:* {len(ainv_bugs)} open  |  *ARPT:* {len(arpt_bugs)} open  |  *AEM:* {len(aem_bugs)} open")
    for i in prerelease[:3]:
        lines.append(f"🟠 *RELEASE BLOCKER:* {_fmt_link(i['key'], i['key'])} — {i['fields']['summary'][:50]}...")
    lines.append("")

    lines.append("*🚦 RELEASE READINESS*")
    lines.append(f"❌ {len(prerelease)} bug(s) targeting unreleased version" if prerelease else "✅ No release blockers")
    lines.append("")

    lines.append("*📌 TOP 3 ACTIONS TODAY*")
    actions = [f"{i+1}. {_fmt_link(item['key'], item['key'])} — Check comments and close/update." for i, item in enumerate(my_items[:3])]
    while len(actions) < 3:
        actions.append(f"{len(actions)+1}. Review open bugs and assign unassigned Critical.")
    lines.extend(actions[:3])
    if recent_changes:
        lines.append("")
        lines.append("*RECENT CHANGES (last 7d)*")
        for i in recent_changes[:5]:
            lines.append(f"• {_fmt_link(i['key'], i['key'])} — {i['fields'].get('summary', '')[:40]}... | {i['fields'].get('status', {}).get('name', '')} | {i['fields'].get('updated', '')[:10]}")
    lines.append("")
    lines.append("*RESOURCES:*")
    lines.append("<https://axsteam.atlassian.net/jira/software/projects/AINV/boards|AINV> | <https://axsteam.atlassian.net/jira/software/projects/ARPT/boards|ARPT> | <https://axsteam.atlassian.net/jira/software/projects/AEM/boards|AEM>")
    lines.append("<https://axsteam.atlassian.net/issues/?jql=project+in+(AINV,ARPT,AEM)+AND+issuetype=Bug+AND+statusCategory+!=+Done|All bugs> | <https://axsteam.atlassian.net/wiki|Confluence>")
    return "\n".join(lines)


def fmt_issue(issue: dict, include_comments: bool = False) -> str:
    f = issue.get("fields", {})
    key = issue["key"]
    proj = f.get("project", {}).get("key", "")
    summary = f.get("summary", "")
    status = f.get("status", {}).get("name", "")
    priority = f.get("priority", {}).get("name", "")
    assignee = f.get("assignee")
    assignee_name = assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
    updated = (f.get("updated") or "")[:10]
    created = (f.get("created") or "")[:10]
    due = (f.get("duedate") or "—")[:10]
    fix_versions = f.get("fixVersions", []) or []
    fv_names = ", ".join(v.get("name", "") for v in fix_versions[:2]) or "—"
    lines = [f"[{key}] {summary} | Status: {status} | Priority: {priority} | Assignee: {assignee_name} | Updated: {updated} | Due: {due} | FixVersion: {fv_names}"]
    if include_comments:
        comments = jira_get_comments(key)
        if comments:
            lines.append("  Comments (recent):")
            for c in comments[-3:]:
                lines.append(f"    - {c['created']} {c['author']}: {c['body'][:120]}...")
    return "\n".join(lines)


def main() -> None:
    print("Fetching Jira data...")
    base_fields = ["summary", "status", "issuetype", "priority", "updated", "project", "assignee", "created", "duedate", "fixVersions"]
    my_items = jira_request(
        f'project in (AINV, ARPT, AEM) AND assignee = "{JEEVAN_ACCOUNT_ID}" AND statusCategory != Done ORDER BY priority DESC, updated DESC',
        base_fields,
    )
    bugs_ainv_arpt = jira_request(
        "project in (AINV, ARPT) AND issuetype = Bug AND statusCategory != Done ORDER BY priority DESC, updated DESC",
        ["summary", "status", "priority", "assignee", "project", "updated", "fixVersions"],
    )
    new_stories = jira_request(
        "project in (AINV, ARPT) AND issuetype = Story AND created >= -14d ORDER BY created DESC",
        ["summary", "status", "priority", "assignee", "created", "project"],
    )
    prerelease = jira_request(
        "project in (AINV, ARPT) AND issuetype = Bug AND statusCategory != Done AND fixVersion in unreleasedVersions() ORDER BY priority DESC",
        ["summary", "status", "priority", "assignee", "fixVersions", "updated"],
    )
    aem_bugs = jira_request(
        "project = AEM AND issuetype = Bug AND statusCategory != Done ORDER BY priority DESC, updated DESC",
        ["summary", "status", "priority", "assignee", "updated"],
    )
    # Blocked issues (status=Blocked) and recently updated (last 7 days)
    blocked_issues = _safe_jira_request(
        "project in (AINV, ARPT, AEM) AND status = Blocked ORDER BY priority DESC, updated DESC",
        ["summary", "status", "priority", "assignee", "project", "updated"],
    )
    recent_changes = jira_request(
        "project in (AINV, ARPT, AEM) AND updated >= -7d ORDER BY updated DESC",
        ["summary", "status", "issuetype", "priority", "assignee", "project", "updated"],
    )

    print("Fetching comments for your items and critical bugs...")
    my_items_with_comments = []
    for i in my_items:
        my_items_with_comments.append(fmt_issue(i, include_comments=True))
    critical_bugs = [i for i in bugs_ainv_arpt if i["fields"].get("priority", {}).get("name") == "Critical"]
    critical_with_comments = [fmt_issue(i, include_comments=True) for i in critical_bugs[:5]]

    print("Searching Confluence for release, blockers, changelog...")
    confluence_release = confluence_search('type=page AND (text~"release" OR text~"schedule" OR text~"AINV" OR text~"ARPT")', limit=8)
    confluence_blockers = confluence_search('type=page AND (text~"blocker" OR text~"blocked" OR text~"known issue")', limit=5)
    confluence_changelog = confluence_search('type=page AND (text~"changelog" OR text~"release notes")', limit=5)
    confluence_content = "\n".join(
        f"- {r['title']}: {r['excerpt']} | {r['url']}" for r in confluence_release
    ) if confluence_release else "(None)"
    confluence_blockers_str = "\n".join(f"- {r['title']}: {r['url']}" for r in confluence_blockers) if confluence_blockers else "(None)"
    confluence_changelog_str = "\n".join(f"- {r['title']}: {r['url']}" for r in confluence_changelog) if confluence_changelog else "(None)"

    context = f"""
=== JIRA: YOUR ITEMS (assigned to Jeevan, not Done) ===
{chr(10).join(my_items_with_comments) if my_items_with_comments else "None"}

=== JIRA: BLOCKED ISSUES (status=Blocked) ===
{chr(10).join(fmt_issue(i) for i in blocked_issues[:10]) if blocked_issues else "None"}

=== JIRA: RECENT CHANGES (updated last 7 days) ===
{chr(10).join(fmt_issue(i) for i in recent_changes[:15]) if recent_changes else "None"}

=== JIRA: CRITICAL BUGS (AINV/ARPT) with recent comments ===
{chr(10).join(critical_with_comments) if critical_with_comments else "None"}

=== JIRA: BUGS TARGETING UNRELEASED VERSION (release blockers) ===
{chr(10).join(fmt_issue(i) for i in prerelease[:5]) if prerelease else "None"}

=== JIRA: NEW STORIES (last 14 days) ===
{chr(10).join(fmt_issue(i) for i in new_stories[:8]) if new_stories else "None"}

=== JIRA: BUG COUNTS ===
AINV: {len([i for i in bugs_ainv_arpt if i["fields"]["project"]["key"] == "AINV"])} open | ARPT: {len([i for i in bugs_ainv_arpt if i["fields"]["project"]["key"] == "ARPT"])} open | AEM: {len(aem_bugs)} open

=== CONFLUENCE: Release/schedule ===
{confluence_content}

=== CONFLUENCE: Blocker/known issue docs ===
{confluence_blockers_str}

=== CONFLUENCE: Changelog/release notes ===
{confluence_changelog_str}

=== SUPPORT LINKS (include all in report) ===
AINV: https://axsteam.atlassian.net/jira/software/projects/AINV/boards
ARPT: https://axsteam.atlassian.net/jira/software/projects/ARPT/boards
AEM: https://axsteam.atlassian.net/jira/software/projects/AEM/boards
All bugs: https://axsteam.atlassian.net/issues/?jql=project+in+(AINV,ARPT,AEM)+AND+issuetype=Bug+AND+statusCategory+!=+Done
My items: https://axsteam.atlassian.net/issues/?jql=assignee+%3D+currentUser()+AND+project+in+(AINV,ARPT,AEM)+AND+statusCategory+!=+Done
Confluence: https://axsteam.atlassian.net/wiki
"""

    system_prompt = """You are an expert sprint analyst for APEX (AINV, ARPT, AEM). Produce a DETAILED, COMPREHENSIVE StandupPulse report. Do NOT miss anything important.

ANALYZE THOROUGHLY:
1. Comments on tickets — what passed, what failed, what needs follow-up, blockers
2. Priorities — what should Jeevan focus on first today
3. Deadlines — due dates, fix versions, scheduled releases
4. Confluence — map release info to Jira tickets, identify risks
5. Risk level — overall risk (HIGH/MEDIUM/LOW) and where to focus first

OUTPUT FORMAT (Slack mrkdwn): 
- *EXECUTIVE SUMMARY* — 3–4 sentences
- *BLOCKERS* — Every blocked issue with link
- *RECENT CHANGES* — Notable updates last 7d
- *YOUR ITEMS* — prioritize by urgency from comments; call out if reviewer feedback needed, tests passed/failed
- *BUGS TO WATCH* — Critical, release blockers, unassigned
- *🚦 RELEASE READINESS* — risk level, what’s blocking release
- *TOP 5 ACTIONS TODAY* — Specific, ordered
- *RESOURCES* — AINV, ARPT, AEM boards, all bugs, my items, Confluence. Format: <url|text>

Use Jira links: <https://axsteam.atlassian.net/browse/KEY|KEY>
Be thorough. Include all support links. Do not skip blockers or recent changes."""

    print("Generating AI report...")
    report = ai_analyze(context, system_prompt)

    if not report:
        print("No AI key (GEMINI_API_KEY or OPENAI_API_KEY). Using basic format.", file=sys.stderr)
        report = _fallback_report(my_items, bugs_ainv_arpt, new_stories, prerelease, aem_bugs, blocked_issues, recent_changes)

    slack_post(report)
    print("✅ StandupPulse posted to Slack.")


if __name__ == "__main__":
    main()
