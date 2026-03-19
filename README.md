# StandupPulse

AI-powered daily standup report. Runs at **6 AM PST** every **Monday–Friday** via GitHub Actions — even when your Mac is off.

**What it does:**
- Fetches your Jira items, bugs, new stories, release blockers (AINV, ARPT, AEM)
- Pulls **comments** on your tickets and critical bugs
- Searches **Confluence** for release/schedule info
- Sends everything to **Google Gemini** (free) for analysis
- AI produces: priorities, risk level, what passed/failed, deadlines, top 3–5 actions for today

## Setup (personal GitHub repo only)

### 1. Create a new repo on your personal GitHub

1. Go to [github.com/new](https://github.com/new)
2. Name it `apex-daily-sprint-report` (or any name)
3. **Important:** Create it under your **personal account**, not an organization
4. Don't initialize with README (we already have files)

### 2. Push this folder to your personal repo

```bash
cd ~/apex-daily-sprint-report
git init
git add .
git commit -m "Add StandupPulse workflow"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/apex-daily-sprint-report.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your personal GitHub username.

### 3. Add secrets to your personal repo

1. Go to **your repo** → **Settings** → **Secrets and variables** → **Actions**
2. Add these 5 secrets:

| Secret | Value |
|--------|-------|
| `JIRA_EMAIL` | `jsaigali@axs.com` |
| `JIRA_API_TOKEN` | Your Atlassian API token |
| `SLACK_BOT_TOKEN` | Your Slack bot token (xoxb-...) |
| `SLACK_CHANNEL` | `D0AMF37Q7JS` |
| `GEMINI_API_KEY` | Free — get at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |

Uses **Google Gemini** (free tier) for AI analysis. No OpenAI or paid account needed. Fallback: basic report if no key.

### 4. Test it

Go to **Actions** → **StandupPulse** → **Run workflow**
