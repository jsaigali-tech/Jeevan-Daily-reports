# One Prompt to Build the Daily Report Automation

**Copy the entire prompt below and paste it into Cursor.** The AI will guide you step-by-step to build your own StandupPulse—no extra questions, just one detail at a time.

---

## THE PROMPT (copy everything below this line)

```
You are going to build a complete StandupPulse automation for me. Follow these rules strictly:

1. DO NOT ask multiple questions at once. Ask for ONE piece of information at a time, wait for my answer, then proceed.
2. Work step-by-step. Complete each step before moving to the next.
3. At the end, you will ask: "Do you want to run this MANUALLY (on demand) or on a SCHEDULE (e.g., 6 AM every weekday)?" Based on my answer:
   - If SCHEDULE: Create a GitHub Actions workflow, then ask for my permission to push the code to a new GitHub repo. If I say yes, guide me to create the repo and push. Then tell me to add secrets (JIRA_EMAIL, JIRA_API_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL, GEMINI_API_KEY) in GitHub Settings → Secrets.
   - If MANUAL: Give me a simple command to run the report whenever I want (e.g., `python3 daily-sprint-report.py` with env vars), and a 1-page "How to Run" guide.

Here is what you will build:

**Scope:** A Python script that:
1. Fetches my Jira items (assigned to me, not done), bugs, new stories, and release blockers from projects I specify
2. Fetches comments on my tickets and critical bugs
3. Optionally searches Confluence for release/schedule info
4. Sends all data to Google Gemini (free API) for AI analysis
5. Posts an AI-generated report to Slack (priorities, risk level, top 3–5 actions for today)

**Tech:** Python 3, stdlib only (urllib, json, no pip install). Use Google Gemini API (free at aistudio.google.com) for AI. Jira + Confluence REST APIs. Slack API.

**Output format:** The AI should produce a Slack-ready report with: Executive Summary, Your Items (with comment context), Bugs to Watch, Release Readiness, Top 3–5 Actions Today, Quick links.

**Reliability (if schedule):** Add retry (3x), timeout, and concurrency to the GitHub Actions workflow so it doesn't skip.

Start by asking me for the FIRST piece of information you need. Go one at a time. Do not list 10 questions. Ask one, get the answer, then ask the next. Build the full solution, then at the very end ask: "Manual or Schedule?" and proceed accordingly.
```

---

## How Your Team Uses This

1. **Copy** the entire prompt (the text inside the code block above)
2. **Paste** into a new Cursor chat
3. **Answer** each question as the AI asks (one at a time)
4. **Choose** Manual or Schedule at the end
5. **Done** — they have their own StandupPulse automation

---

## What the AI Will Ask For (typical order)

| Step | What the AI asks |
|------|------------------|
| 1 | Jira base URL (e.g., https://yourcompany.atlassian.net) |
| 2 | Jira project keys (e.g., AINV, ARPT, AEM) |
| 3 | Your Jira account ID (or email for assignee filter) |
| 4 | Confluence base URL (usually same domain + /wiki) |
| 5 | Slack channel ID or name |
| 6 | Where to save the files (folder path) |
| 7 | Manual or Schedule? |
| 8 | (If Schedule) Permission to push to GitHub? |

---

## Share This With Your Team

- **File:** `docs/ONE-PROMPT-TO-BUILD-ALL.md`
- **Link:** [View on GitHub](https://github.com/jsaigali-tech/Jeevan-Daily-reports/blob/main/docs/ONE-PROMPT-TO-BUILD-ALL.md)

They only need this one prompt. No prior setup. No extra docs.
