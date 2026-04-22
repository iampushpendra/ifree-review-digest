"""
Daily Play Store low-star review digest → Slack DM.
Includes AI-generated semantic insights via OpenAI.

Required env vars:
  PLAY_STORE_APP_ID  — e.g. com.ifreed
  SLACK_BOT_TOKEN    — xoxb-... bot token with chat:write + im:write scopes
  SLACK_USER_ID      — Slack user ID to DM (e.g. U012AB3CD)
  OPENAI_API_KEY     — for semantic analysis and insights
"""

import json
import os
from datetime import datetime, timedelta, timezone

from google_play_scraper import Sort, reviews
from openai import OpenAI
from slack_sdk import WebClient

APP_ID = os.environ["PLAY_STORE_APP_ID"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_USER_ID = os.environ["SLACK_USER_ID"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

LOW_STAR_RATINGS = {1, 2, 3}
DAYS_BACK = 7
MAX_SHOWN = 8


# ── 1. Fetch reviews ─────────────────────────────────────────────────────────

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
                return collected  # newest-first — safe to stop here

            if r["score"] in LOW_STAR_RATINGS:
                collected.append(r)

        if not continuation_token:
            break

    return collected


# ── 2. AI insights ───────────────────────────────────────────────────────────

def generate_insights(low_star: list[dict]) -> dict:
    """
    Returns a dict with keys:
      summary        — 2-3 sentence executive summary
      themes         — list of {title, count, severity, description}
      top_issues     — list of short actionable strings
      positive_notes — list of any silver linings mentioned
    """
    if not low_star:
        return {
            "summary": "No low-star reviews this week. Keep it up!",
            "themes": [],
            "top_issues": [],
            "positive_notes": [],
        }

    reviews_text = "\n\n".join(
        f"[{r['score']}★] {r['content']}" for r in low_star
    )

    prompt = f"""You are a product analyst for iFreed, a mental health / therapy app.
Below are {len(low_star)} low-star (1–3 star) Play Store reviews from the last 7 days.

Analyse them and respond with a JSON object (no markdown, raw JSON only) with exactly these keys:

{{
  "summary": "<2-3 sentence executive summary of the week's user pain>",
  "themes": [
    {{
      "title": "<short theme name>",
      "count": <number of reviews mentioning this>,
      "severity": "<critical|high|medium>",
      "description": "<1 sentence describing the pattern>"
    }}
  ],
  "top_issues": ["<actionable issue 1>", "<actionable issue 2>", ...],
  "positive_notes": ["<any silver lining or positive mention>", ...]
}}

Rules:
- themes: list the top 3-5 themes, ordered by count descending
- top_issues: max 5, each under 12 words, phrased as engineering/product action items
- positive_notes: only include if genuinely present; empty list if none
- Be specific — reference actual feature names or flows mentioned in reviews

REVIEWS:
{reviews_text}
"""

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


# ── 3. Build Slack blocks ────────────────────────────────────────────────────

SEVERITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡"}


def build_blocks(low_star: list[dict], insights: dict) -> list[dict]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DAYS_BACK)

    star_counts = {1: 0, 2: 0, 3: 0}
    for r in low_star:
        star_counts[r["score"]] += 1
    total = len(low_star)

    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "📱 iFreed — Low-Star Review Digest (Last 7 Days)"},
    })

    # Stats row
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"*Period:* {cutoff.strftime('%b %d')} – {now.strftime('%b %d, %Y')}  |  "
                f"*Total:* {total} review(s)\n"
                f"⭐ 1-star: *{star_counts[1]}*  ·  "
                f"⭐⭐ 2-star: *{star_counts[2]}*  ·  "
                f"⭐⭐⭐ 3-star: *{star_counts[3]}*"
            ),
        },
    })

    blocks.append({"type": "divider"})

    if total == 0:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "_No low-star reviews this week. 🎉_"},
        })
        return blocks

    # ── AI Summary ──
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*🧠 AI Summary*\n{insights['summary']}"},
    })

    # ── Themes ──
    if insights.get("themes"):
        theme_lines = []
        for t in insights["themes"]:
            emoji = SEVERITY_EMOJI.get(t.get("severity", "medium"), "🟡")
            theme_lines.append(
                f"{emoji} *{t['title']}* ({t['count']} reviews) — {t['description']}"
            )
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*📊 Recurring Themes*\n" + "\n".join(theme_lines)},
        })

    # ── Top Issues ──
    if insights.get("top_issues"):
        issue_lines = [f"• {issue}" for issue in insights["top_issues"]]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🔧 Top Action Items*\n" + "\n".join(issue_lines)},
        })

    # ── Positive Notes ──
    if insights.get("positive_notes"):
        note_lines = [f"• {note}" for note in insights["positive_notes"]]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*✅ Silver Linings*\n" + "\n".join(note_lines)},
        })

    blocks.append({"type": "divider"})

    # ── Individual Reviews ──
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*📝 Recent Reviews* (showing {min(total, MAX_SHOWN)} of {total})"},
    })

    for r in low_star[:MAX_SHOWN]:
        stars = "⭐" * r["score"]
        date_str = r["at"].strftime("%b %d")
        content = r["content"]
        if len(content) > 280:
            content = content[:280] + "…"
        text = f"*{stars}* _{r.get('userName', 'Anonymous')}_ · {date_str}\n>{content}"

        reply = r.get("replyContent") or ""
        if reply:
            reply_short = reply[:180] + ("…" if len(reply) > 180 else "")
            text += f"\n>*Dev reply:* {reply_short}"

        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    if total > MAX_SHOWN:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"_…and {total - MAX_SHOWN} more. <https://play.google.com/console|Open Play Console> for the full list._",
            },
        })

    return blocks


# ── 4. Send to Slack ─────────────────────────────────────────────────────────

def send_to_slack(blocks: list[dict]) -> None:
    client = WebClient(token=SLACK_BOT_TOKEN)
    dm = client.conversations_open(users=[SLACK_USER_ID])
    channel_id = dm["channel"]["id"]
    client.chat_postMessage(
        channel=channel_id,
        blocks=blocks,
        text="iFreed Play Store low-star review digest",
    )


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Fetching reviews for {APP_ID}...")
    low_star = fetch_low_star_reviews()
    print(f"Found {len(low_star)} low-star review(s) in last {DAYS_BACK} days")

    print("Generating AI insights...")
    insights = generate_insights(low_star)
    print(f"Themes identified: {[t['title'] for t in insights.get('themes', [])]}")

    blocks = build_blocks(low_star, insights)
    send_to_slack(blocks)
    print("Digest sent to Slack.")
