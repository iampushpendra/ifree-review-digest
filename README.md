# iFreed Play Store Review Digest

Weekly Slack digest of all Play Store reviews for the iFreed app, delivered every **Monday at 12:00 PM IST** via GitHub Actions.

## What it does

- Runs weekly, every Monday at 12:00 PM IST (6:30 AM UTC)
- Fetches all Play Store reviews (every rating, 1–5 stars) from the last 7 days
- Posts a formatted message to a Slack channel with a star-count summary, average rating, and AI insights, plus every individual review threaded below (chunked to stay under Slack's block limit)

## Setup

### 1. Find your Play Store app package name
Open the app's Play Store URL — the part after `id=` is the package name (e.g. `care.freed.ifree`).

### 2. Create a Slack app
1. Go to https://api.slack.com/apps → **Create New App** → From scratch
2. Under **OAuth & Permissions**, add scope: `chat:write`
3. **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
4. Invite the bot to the target channel: in that channel, run `/invite @<bot-name>`
5. Find the channel ID: open the channel → click its name → the ID is at the bottom of the **About** tab (e.g. `C0123ABCD`)

### 3. Add GitHub Actions secrets & variables
Go to **Settings → Secrets and variables → Actions**:

| Name | Kind | Value |
|---|---|---|
| `SLACK_BOT_TOKEN` | Secret | `xoxb-...` |
| `OPENAI_API_KEY` | Secret | `sk-...` |
| `PLAY_STORE_APP_ID` | Variable | e.g. `care.freed.ifree` |
| `SLACK_CHANNEL_ID` | Variable | e.g. `C0123ABCD` |

> To DM a user instead of posting to a channel, set a `SLACK_USER_ID` variable and leave `SLACK_CHANNEL_ID` unset (requires the `im:write` scope).

### 4. Test manually
Go to **Actions → Play Store Review Digest → Run workflow** to trigger a test run before waiting for the scheduled time.
