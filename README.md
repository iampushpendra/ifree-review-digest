# iFreed Play Store Review Digest

Daily Slack digest of 1–3 star Play Store reviews for the iFreed app, delivered at **10:00 AM IST** via GitHub Actions.

## What it does

- Runs every day at 10:00 AM IST (4:30 AM UTC)
- Fetches all 1, 2, and 3-star Play Store reviews from the last 7 days
- Sends a formatted Slack DM with a star-count summary + up to 10 individual reviews

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
