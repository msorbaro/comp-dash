"""Assigns a content category to every post that doesn't have one yet, using
Claude (Haiku) against the taxonomy in docs/content_taxonomy.md.
"""
import json
import os

import anthropic

from db.connection import get_conn

CATEGORIES = [
    "Product Feature / New Arrival",
    "Promotion / Sale / Discount",
    "Educational / How-To / Tips",
    "Behind-the-Scenes / Culture",
    "UGC / Customer Testimonial",
    "Holiday / Seasonal",
    "Community / Cause Marketing",
    "Brand / Lifestyle / Awareness",
    "Meme / Trending / Entertainment",
    "Announcement / News",
    "Contest / Giveaway",
    "Influencer / Partnership Collab",
    "Other",
]

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = f"""You classify a single Instagram post into exactly one category
from this fixed list, based on its caption and post type:

{chr(10).join(f"- {c}" for c in CATEGORIES)}

Reply with ONLY a JSON object: {{"category": "<one of the exact category names above>", "confidence": "high|medium|low"}}
No other text."""


def classify_pending_posts(batch_size: int = 200) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    conn = get_conn()
    stats = {"classified": 0, "errors": 0}

    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, caption, post_type FROM posts WHERE category IS NULL LIMIT %s",
                (batch_size,),
            )
            pending = cur.fetchall()

        for post_id, caption, post_type in pending:
            user_content = f"Post type: {post_type}\nCaption: {caption or '(no caption)'}"
            try:
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=100,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_content}],
                )
                raw_text = resp.content[0].text.strip()
                if raw_text.startswith("```"):
                    raw_text = raw_text.strip("`")
                    raw_text = raw_text[raw_text.find("{"):raw_text.rfind("}") + 1]
                parsed = json.loads(raw_text)
                category = parsed["category"]
                confidence = parsed.get("confidence", "medium")
                if category not in CATEGORIES:
                    category, confidence = "Other", "low"
            except Exception:  # noqa: BLE001 - never let one bad post kill the whole batch
                category, confidence = "Other", "low"
                stats["errors"] += 1

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE posts SET category = %s, category_confidence = %s WHERE id = %s",
                    (category, confidence, post_id),
                )
            stats["classified"] += 1

    return stats
