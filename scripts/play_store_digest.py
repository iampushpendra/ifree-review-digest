"""
Daily Play Store low-star review digest → Slack DM.

Required env vars:
  PLAY_STORE_APP_ID  — e.g. care.freed.ifree
  SLACK_BOT_TOKEN    — xoxb-... bot token with chat:write + im:write scopes
  SLACK_USER_ID      — Slack user ID to DM (e.g. U012AB3CD)
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from google_play_scraper import Sort, reviews
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

APP_ID = os.environ["PLAY_STORE_APP_ID"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_USER_ID = os.environ["SLACK_USER_ID"]

LOW_STAR_RATINGS = {1, 2, 3}
DAYS_BACK = 7
MAX_SHOWN = 10


def fetch_low_star_reviews() -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    collected: list[dict] = []
    continuation_token = None

    while True:
        result, continuation_token = reviews(
            APP_ID,
            lang="en",
            country="in",
            sort=Sort.NEWEST,
            count=200,
            continuation_token=continuation_token,
        )

        if not result:
            break

        for r in result:
            review_date = r["at"]
            if review_date.tzinfo is None:
                review_date = review_date.replace(tzinfo=timezone.utc)

            if review_date < cutoff:
                return collected  # reviews are newest-first; stop early

            if r["score"] in LOW_STAR_RATINGS:
                collected.append(r)

        if not continuation_token:
            break

    return collected


def build_blocks(low_star: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DAYS_BACK)

    star_counts = {1: 0, 2: 0, 3: 0}
    for r in low_star:
        star_counts[r["score"]] += 1

    total = len(low_star)

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📱 iFreed — Low-Star Play Store Reviews (Last 7 Days)",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Period:* {cutoff.strftime('%b %d')} – {now.strftime('%b %d, %Y')}\n"
                    f"*Total:* {total} review(s)\n"
                    f"⭐ 1-star: *{star_counts[1]}*  |  "
                    f"⭐⭐ 2-star: *{star_counts[2]}*  |  "
                    f"⭐⭐⭐ 3-star: *{star_counts[3]}*"
                ),
            },
        },
        {"type": "divider"},
    ]

    if total == 0:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No low-star reviews in the last 7 days. 🎉_",
                },
            }
        )
        return blocks

    for r in low_star[:MAX_SHOWN]:
        stars = "⭐" * r["score"]
        date_str = r["at"].strftime("%b %d, %Y")
        content = r["content"]
        if len(content) > 350:
            content = content[:350] + "…"
        text = f"*{stars}* — _{r.get('userName', 'Anonymous')}_ · {date_str}\n>{content}"

        reply = r.get("replyContent") or ""
        if reply:
            reply_short = reply[:200] + ("…" if len(reply) > 200 else "")
            text += f"\n>*Dev reply:* {reply_short}"

        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": text}}
        )

    if total > MAX_SHOWN:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_…and {total - MAX_SHOWN} more. Open Play Console for the full list._",
                },
            }
        )

    return blocks


def send_to_slack(blocks: list[dict]) -> None:
    client = WebClient(token=SLACK_BOT_TOKEN)
    dm = client.conversations_open(users=[SLACK_USER_ID])
    channel_id = dm["channel"]["id"]
    client.chat_postMessage(
        channel=channel_id,
        blocks=blocks,
        text="iFreed Play Store low-star review digest",
    )


if __name__ == "__main__":
    print(f"Fetching reviews for {APP_ID}...")
    low_star = fetch_low_star_reviews()
    print(f"Found {len(low_star)} low-star review(s) in last {DAYS_BACK} days")
    blocks = build_blocks(low_star)
    send_to_slack(blocks)
    print("Digest sent to Slack.")
