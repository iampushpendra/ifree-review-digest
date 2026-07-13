"""
Weekly Play Store review digest (all ratings) → Slack DM.
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

DAYS_BACK = 7
MAX_SHOWN = 8


# ── 1. Fetch reviews ─────────────────────────────────────────────────────────

def fetch_reviews() -> list[dict]:
    """Fetch all reviews (every rating) from the last DAYS_BACK days."""
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

            collected.append(r)

        if not continuation_token:
            break

    return collected


# ── 2. AI insights ───────────────────────────────────────────────────────────

def generate_insights(all_reviews: list[dict]) -> dict:
    """
    Returns a dict with keys:
      summary        — 2-3 sentence executive summary
      themes         — list of {title, count, severity, description}
      top_issues     — list of short actionable strings
      positive_notes — list of things users praised
    """
    if not all_reviews:
        return {
            "summary": "No reviews this week.",
            "themes": [],
            "top_issues": [],
            "positive_notes": [],
        }

    reviews_text = "\n\n".join(
        f"[{r['score']}★] {r['content']}" for r in all_reviews
    )

    prompt = f"""You are a product analyst for iFreed, a mental health / therapy app.
Below are {len(all_reviews)} Play Store reviews (all ratings, 1–5 stars) from the last 7 days.

Analyse the full spread of sentiment and respond with a JSON object (no markdown, raw JSON only) with exactly these keys:

{{
  "summary": "<2-3 sentence executive summary of overall user sentiment this week, covering both what users love and where they struggle>",
  "themes": [
    {{
      "title": "<short theme name>",
      "count": <number of reviews mentioning this>,
      "severity": "<critical|high|medium|positive>",
      "description": "<1 sentence describing the pattern>"
    }}
  ],
  "top_issues": ["<actionable issue 1>", "<actionable issue 2>", ...],
  "positive_notes": ["<what users praised 1>", "<what users praised 2>", ...]
}}

Rules:
- themes: list the top 3-5 themes across ALL reviews, ordered by count descending; use severity "positive" for praise themes and critical/high/medium for problems
- top_issues: max 5, each under 12 words, phrased as engineering/product action items (drawn from the negative/critical reviews)
- positive_notes: what users genuinely liked; empty list if none
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

SEVERITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "positive": "🟢"}


def compute_star_stats(all_reviews: list[dict]) -> tuple[dict, float]:
    """Return per-rating counts (1-5) and the average rating."""
    star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in all_reviews:
        star_counts[r["score"]] += 1
    total = len(all_reviews)
    avg = sum(s * c for s, c in star_counts.items()) / total if total else 0.0
    return star_counts, avg


def build_main_blocks(all_reviews: list[dict], insights: dict) -> list[dict]:
    """Main message: stats + AI insights only."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DAYS_BACK)

    star_counts, avg = compute_star_stats(all_reviews)
    total = len(all_reviews)

    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "📱 iFreed — Weekly Review Digest (Last 7 Days)"},
    })

    # Stats row
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"*Period:* {cutoff.strftime('%b %d')} – {now.strftime('%b %d, %Y')}  |  "
                f"*Total:* {total} review(s)  |  *Avg:* {avg:.1f}★\n"
                f"⭐ 1: *{star_counts[1]}*  ·  "
                f"⭐ 2: *{star_counts[2]}*  ·  "
                f"⭐ 3: *{star_counts[3]}*  ·  "
                f"⭐ 4: *{star_counts[4]}*  ·  "
                f"⭐ 5: *{star_counts[5]}*"
            ),
        },
    })

    blocks.append({"type": "divider"})

    if total == 0:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "_No reviews this week._"},
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
            "text": {"type": "mrkdwn", "text": "*✅ What Users Loved*\n" + "\n".join(note_lines)},
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"_💬 {total} review(s) attached in thread below_"},
    })

    return blocks


# Slack allows at most 50 blocks per message; chunk well under that.
THREAD_CHUNK_SIZE = 45


def _review_block(r: dict) -> dict:
    stars = "⭐" * r["score"]
    date_str = r["at"].strftime("%b %d, %Y")
    content = r["content"]
    if len(content) > 350:
        content = content[:350] + "…"
    text = f"*{stars}* _{r.get('userName', 'Anonymous')}_ · {date_str}\n>{content}"

    reply = r.get("replyContent") or ""
    if reply:
        reply_short = reply[:200] + ("…" if len(reply) > 200 else "")
        text += f"\n>*Dev reply:* {reply_short}"

    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def build_thread_messages(all_reviews: list[dict]) -> list[list[dict]]:
    """
    Thread replies: all individual reviews, split into multiple messages so no
    single message exceeds Slack's 50-block limit. Returns a list of block lists.
    """
    total = len(all_reviews)
    messages: list[list[dict]] = []

    for i in range(0, total, THREAD_CHUNK_SIZE):
        chunk = all_reviews[i:i + THREAD_CHUNK_SIZE]
        part = i // THREAD_CHUNK_SIZE + 1
        parts = (total + THREAD_CHUNK_SIZE - 1) // THREAD_CHUNK_SIZE
        header = f"📝 All Reviews ({total})" if parts == 1 else f"📝 All Reviews ({total}) — part {part}/{parts}"
        blocks: list[dict] = [
            {"type": "header", "text": {"type": "plain_text", "text": header}}
        ]
        blocks.extend(_review_block(r) for r in chunk)
        messages.append(blocks)

    return messages


# ── 4. Write Obsidian note ───────────────────────────────────────────────────

SEVERITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "positive": "🟢"}


def write_obsidian_note(all_reviews: list[dict], insights: dict, output_path: str) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DAYS_BACK)

    star_counts, avg = compute_star_stats(all_reviews)
    total = len(all_reviews)

    lines = [
        f"---",
        f"date: {now.strftime('%Y-%m-%d')}",
        f"tags: [play-store, reviews, digest]",
        f"---",
        f"",
        f"# iFreed Play Store Digest — {now.strftime('%b %d, %Y')}",
        f"",
        f"**Period:** {cutoff.strftime('%b %d')} – {now.strftime('%b %d, %Y')}  |  **Total:** {total} review(s)  |  **Avg:** {avg:.1f}★",
        f"⭐ 1: **{star_counts[1]}** · ⭐ 2: **{star_counts[2]}** · ⭐ 3: **{star_counts[3]}** · ⭐ 4: **{star_counts[4]}** · ⭐ 5: **{star_counts[5]}**",
        f"",
        f"## 🧠 AI Summary",
        f"",
        f"{insights['summary']}",
        f"",
    ]

    if insights.get("themes"):
        lines += ["## 📊 Recurring Themes", ""]
        for t in insights["themes"]:
            icon = SEVERITY_ICON.get(t.get("severity", "medium"), "🟡")
            lines.append(f"- {icon} **{t['title']}** ({t['count']} reviews) — {t['description']}")
        lines.append("")

    if insights.get("top_issues"):
        lines += ["## 🔧 Action Items", ""]
        for issue in insights["top_issues"]:
            lines.append(f"- {issue}")
        lines.append("")

    if insights.get("positive_notes"):
        lines += ["## ✅ What Users Loved", ""]
        for note in insights["positive_notes"]:
            lines.append(f"- {note}")
        lines.append("")

    if all_reviews:
        lines += ["## 📝 All Reviews", ""]
        for r in all_reviews:
            stars = "⭐" * r["score"]
            date_str = r["at"].strftime("%b %d, %Y")
            content = r["content"].replace("\n", " ")
            lines.append(f"### {stars} {r.get('userName', 'Anonymous')} · {date_str}")
            lines.append(f"")
            lines.append(f"> {content}")
            reply = r.get("replyContent") or ""
            if reply:
                lines.append(f"")
                lines.append(f"> **Dev reply:** {reply.replace(chr(10), ' ')}")
            lines.append("")

    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Obsidian note written to {output_path}")


# ── 5. Send to Slack ─────────────────────────────────────────────────────────

def send_to_slack(main_blocks: list[dict], thread_messages: list[list[dict]]) -> None:
    client = WebClient(token=SLACK_BOT_TOKEN)
    dm = client.conversations_open(users=[SLACK_USER_ID])
    channel_id = dm["channel"]["id"]

    # Post main digest message
    resp = client.chat_postMessage(
        channel=channel_id,
        blocks=main_blocks,
        text="iFreed Play Store weekly review digest",
    )

    # Post all reviews as one or more thread replies (chunked under Slack's block limit)
    for blocks in thread_messages:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=resp["ts"],
            blocks=blocks,
            text="Full review list",
        )


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Fetching reviews for {APP_ID}...")
    all_reviews = fetch_reviews()
    print(f"Found {len(all_reviews)} review(s) in last {DAYS_BACK} days")

    print("Generating AI insights...")
    insights = generate_insights(all_reviews)
    print(f"Themes identified: {[t['title'] for t in insights.get('themes', [])]}")

    main_blocks = build_main_blocks(all_reviews, insights)
    thread_messages = build_thread_messages(all_reviews) if all_reviews else []
    send_to_slack(main_blocks, thread_messages)
    print("Digest sent to Slack.")

    note_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    write_obsidian_note(all_reviews, insights, f"vault-output/projects/ifree-reviews/{note_date}.md")
    print("Obsidian note written.")
