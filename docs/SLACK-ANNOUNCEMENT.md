# Slack Announcement — Daily Report Automation

**Copy the message below and paste it into your team Slack channel, then attach your demo video.**

---

## THE MESSAGE

```
hey team

so i built this daily report thing that dumps into slack — basically pulls my jira stuff, bugs, release blockers, comments, and puts it all in one message. been using it for a bit and it's actually helped me not scramble right before standups

it grabs data from jira (and confluence for release info) based on filters — your items, open bugs, unreleased stuff, etc. then formats it and posts

you can do it two ways: scheduled at 6am on weekdays (just filtered data, no ai) or on-demand in cursor — type "run my daily report" and it uses ai to actually analyze everything and tell you what to focus on. i use both depending on the day

[attach your video]

if anyone wants to set up their own — i wrote a prompt you can paste into cursor and it walks you through it. links below. lmk if you hit any snags

https://github.com/jsaigali-tech/Jeevan-Daily-reports/blob/main/docs/ONE-PROMPT-TO-BUILD-ALL.md
https://github.com/jsaigali-tech/Jeevan-Daily-reports
```

---

## Tips for Your Recording

1. **Start** — Cursor chat open, show the prompt or "Run daily report"
2. **Trigger** — Go to GitHub Actions → Run workflow
3. **Result** — Switch to Slack, show the notification and report content
4. **Keep it short** — 1–2 minutes is enough
