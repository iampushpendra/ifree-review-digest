# iFreed Play Store Review Digest

Weekly Slack digest of all Play Store reviews for the iFreed app, delivered every **Monday at 12:00 PM IST** via GitHub Actions.

## What it does

- Runs weekly, every Monday at 12:00 PM IST (6:30 AM UTC)
- Fetches all Play Store reviews (every rating, 1–5 stars) from the last 7 days
- Sends a formatted Slack DM with a star-count summary, average rating, and AI insights, plus every individual review threaded below (chunked to stay under Slack's block limit)

## Setup

### 1. Find your Play Store app package name
Open the app's Play Store URL — the part after `id=` is the package name (e.g. `care.freed.ifree`).

### 2. Create a Slack app
1. Go to https://api.slack.com/apps → **Create New App** → From scratch
2. Under **OAuth & Permissions**, add scopes: `chat:write`, `im:write`
3. **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
4. Find your Slack user ID: click your profile in Slack → `⋮` → **Copy member ID**

### 3. Add GitHub Actions secrets
Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `PLAY_STORE_APP_ID` | e.g. `care.freed.ifree` |
| `SLACK_BOT_TOKEN` | `xoxb-...` |
| `SLACK_USER_ID` | e.g. `U012AB3CD` |

### 4. Test manually
Go to **Actions → Play Store Review Digest → Run workflow** to trigger a test run before waiting for the scheduled time.
