"""Assigns a content category to posts (Instagram, TikTok, YouTube, X) using
Claude (Haiku) against the taxonomy in docs/content_taxonomy.md.
"""
import json
import os

import anthropic

from categorize.funnel_taxonomy import FUNNEL_STAGES, FUNNEL_SYSTEM_PROMPT
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

SYSTEM_PROMPT = f"""You classify a single social media post into exactly one category
from this fixed list, based on its caption/text and post type:

{chr(10).join(f"- {c}" for c in CATEGORIES)}

Reply with ONLY a JSON object: {{"category": "<one of the exact category names above>", "confidence": "high|medium|low"}}
No other text."""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def classify_caption(caption: str, post_type: str = "") -> tuple:
    """Returns (category, confidence). Falls back to ("Other", "low") on any
    failure so one bad post never crashes a batch run. Reused by Instagram,
    TikTok, YouTube, and X ingestion.
    """
    user_content = f"Post type: {post_type or 'unknown'}\nCaption: {caption or '(no caption)'}"
    try:
        resp = _get_client().messages.create(
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
            return "Other", "low"
        return category, confidence
    except Exception:  # noqa: BLE001
        return "Other", "low"


def classify_funnel_stage(text: str, category: str = "", context: str = "") -> tuple:
    """Classifies a piece of text content into the See/Think/Do framework
    (see categorize/funnel_taxonomy.py). Returns (stage, confidence), falling
    back to ("Think", "low") - the middle/default stage - on any failure.
    """
    user_content = (
        f"Content type: {context or 'social media post'}\n"
        f"Assigned content category (for reference): {category or 'unknown'}\n"
        f"Text: {text or '(no text)'}"
    )
    try:
        resp = _get_client().messages.create(
            model=MODEL,
            max_tokens=80,
            system=FUNNEL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        raw_text = resp.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            raw_text = raw_text[raw_text.find("{"):raw_text.rfind("}") + 1]
        parsed = json.loads(raw_text)
        stage = parsed["stage"]
        confidence = parsed.get("confidence", "medium")
        if stage not in FUNNEL_STAGES:
            return "Think", "low"
        return stage, confidence
    except Exception:  # noqa: BLE001
        return "Think", "low"


def classify_pending_posts(batch_size: int = 200, commit_every: int = 25) -> dict:
    """Classifies up to batch_size pending Instagram posts, committing every
    `commit_every` posts so a crash/timeout partway through a large batch
    doesn't lose already-classified work (each API call already costs money).
    """
    conn = get_conn()
    stats = {"classified": 0, "errors": 0}

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, caption, post_type FROM posts WHERE category IS NULL LIMIT %s",
            (batch_size,),
        )
        pending = cur.fetchall()
    conn.commit()

    for post_id, caption, post_type in pending:
        category, confidence = classify_caption(caption, post_type)
        if confidence == "low" and category == "Other":
            stats["errors"] += 1

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE posts SET category = %s, category_confidence = %s WHERE id = %s",
                (category, confidence, post_id),
            )
        stats["classified"] += 1

        if stats["classified"] % commit_every == 0:
            conn.commit()

    conn.commit()
    return stats
