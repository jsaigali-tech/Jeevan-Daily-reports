# Slack Announcement — Daily Report Automation

**Copy the message below and paste it into your team Slack channel, then attach your demo video.**

---

## THE MESSAGE

```
Hey team,

I put together a daily sprint report thing and thought I'd share it. Basically it pulls your Jira items, bugs, release blockers, and comments, then sends a summary to Slack so you can get up to speed before standups without digging through tickets.

Here's how it works: it fetches data from Jira (and Confluence for release info) based on filters — your assigned items, open bugs, stuff targeting unreleased versions, etc. Then it formats that into a report and posts it.

You can run it two ways:

**1. Trigger-based (scheduled)** — Runs automatically at 6 AM on weekdays. In this mode it uses filters to pull the data and formats it into a report. No AI analysis, just the structured data you need. Good if you want something in your inbox every morning without thinking about it.

**2. On-demand (Cursor)** — When you're in Cursor and type something like "Run my daily report," it uses the full AI to actually analyze everything — comments, priorities, what passed/failed, where to focus. That's when you get the smarter, more contextual summary.

So: scheduled = filtered data, formatted. On-demand = AI digs in and tells you what matters. Whichever fits your workflow.

[Attach your demo video here]

If you want to set up your own, I wrote a single prompt you can paste into Cursor — it walks you through everything step by step. Link below. Happy to help if you run into anything.

Prompt: https://github.com/jsaigali-tech/Jeevan-Daily-reports/blob/main/docs/ONE-PROMPT-TO-BUILD-ALL.md
Repo: https://github.com/jsaigali-tech/Jeevan-Daily-reports
```

---

## Tips for Your Recording

1. **Start** — Cursor chat open, show the prompt or “Run daily report”
2. **Trigger** — Go to GitHub Actions → Run workflow
3. **Result** — Switch to Slack, show the notification and report content
4. **Keep it short** — 1–2 minutes is enough
