"""Multi-label aspect-theme extraction for voice.reddit_mentions - the same
taxonomy and (theme, sentiment)-pair design as categorize/review_themes.py,
reused as-is since Reddit mentions are about the same tire/auto-repair
brands. Distinct from the `theme` column already on voice.reddit_mentions
(that one is post-PURPOSE - complaint/question/recommendation/etc., set by
categorize/reddit_sentiment.py) - this is post-ASPECT (price, speed,
honesty, etc.), written to the separate voice.reddit_mention_themes table
since one mention can surface several aspects at once.

Only classifies mentions already judged relevant (is_relevant) - an
irrelevant mention has nothing real to theme.
"""
from __future__ import annotations

import json
import os
import time

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from categorize.review_themes import THEMES, THEME_KEYS, _THEME_LIST_TEXT  # noqa: F401 - same taxonomy, reused
from db.connection import get_conn

MODEL = "claude-haiku-4-5"
CHUNK_SIZE = 12_000
WRITE_COMMIT_BATCH = 500
POLL_SECONDS = 20

SYSTEM_PROMPT = f"""You read a single Reddit post or comment about a specific car repair/tire brand and identify which specific aspects of the experience it actually discusses, with the sentiment toward EACH aspect separately - a post can be positive about one thing and negative about another (e.g. "fast service but overpriced" is positive on speed, negative on price).

Pick 1-3 of the most salient themes actually discussed below - not every theme that could theoretically apply, just what this specific post/comment is really about. Only return an empty list if there's no substantive content to theme (e.g. a one-line joke, or a post that doesn't actually describe an experience).

Themes (use these exact keys):
{_THEME_LIST_TEXT}

Reply with ONLY a JSON object:
{{"themes": [{{"theme": "<key>", "sentiment": "positive|neutral|negative"}}, ...]}}
0 to 3 items. No other text."""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _count_pending() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT count(*) FROM voice.reddit_mentions
                WHERE is_relevant AND aspect_themed_at IS NULL AND (text IS NOT NULL OR title IS NOT NULL)
            """)
            return cur.fetchone()[0]


def _fetch_pending_chunk(limit: int) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rm.mention_id, vb.name, rm.title, rm.text
                FROM voice.reddit_mentions rm JOIN voice.brands vb ON vb.brand_id = rm.brand_id
                WHERE rm.is_relevant AND rm.aspect_themed_at IS NULL
                  AND (rm.text IS NOT NULL OR rm.title IS NOT NULL)
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
    return [{"mention_id": r, "brand_name": name, "title": title, "text": text} for r, name, title, text in rows]


def _run_one_batch(client: anthropic.Anthropic, rows: list[dict]) -> dict:
    requests = []
    for r in rows:
        content = f"Brand: {r['brand_name']}\nTitle: {r['title'] or '(none - this is a comment)'}\nText: {r['text'] or '(no text)'}"
        requests.append(Request(
            custom_id=str(r["mention_id"]),
            params=MessageCreateParamsNonStreaming(
                model=MODEL, max_tokens=250, system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            ),
        ))
    batch = client.messages.batches.create(requests=requests)
    print(f"Created batch {batch.id} ({len(requests)} mentions)", flush=True)

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        print(
            f"  batch {batch.id}: {batch.processing_status} "
            f"(processing={batch.request_counts.processing}, succeeded={batch.request_counts.succeeded})",
            flush=True,
        )
        time.sleep(POLL_SECONDS)

    parsed: dict[int, list[dict]] = {}
    n_failed = 0
    for result in client.messages.batches.results(batch.id):
        mention_id = int(result.custom_id)
        if result.result.type != "succeeded":
            n_failed += 1
            continue
        text = next(
            (b.text for b in result.result.message.content if b.type == "text"), ""
        ).strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.find("{"):text.rfind("}") + 1]
        try:
            data = json.loads(text)
            themes = []
            for t in data.get("themes", []):
                theme, sentiment = t.get("theme"), t.get("sentiment")
                if theme in THEME_KEYS and sentiment in ("positive", "neutral", "negative"):
                    themes.append({"theme": theme, "sentiment": sentiment})
        except Exception:  # noqa: BLE001
            n_failed += 1
            continue
        parsed[mention_id] = themes[:3]

    n_written, n_theme_rows = 0, 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for mention_id, themes in parsed.items():
                cur.execute("DELETE FROM voice.reddit_mention_themes WHERE mention_id = %s", (mention_id,))
                for t in themes:
                    cur.execute(
                        """INSERT INTO voice.reddit_mention_themes (mention_id, theme, theme_sentiment)
                           VALUES (%s, %s, %s) ON CONFLICT (mention_id, theme) DO NOTHING""",
                        (mention_id, t["theme"], t["sentiment"]),
                    )
                    n_theme_rows += 1
                cur.execute("UPDATE voice.reddit_mentions SET aspect_themed_at = now() WHERE mention_id = %s", (mention_id,))
                n_written += 1
                if n_written % WRITE_COMMIT_BATCH == 0:
                    conn.commit()
        conn.commit()
    finally:
        conn.close()

    return {"n_written": n_written, "n_theme_rows": n_theme_rows, "n_failed": n_failed}


def classify_pending() -> dict:
    """Themes every relevant voice.reddit_mentions row with aspect_themed_at
    still NULL, walking the backlog in CHUNK_SIZE-row slices."""
    n_pending = _count_pending()
    client = _get_client()
    n_written, n_theme_rows, n_failed = 0, 0, 0

    while True:
        chunk = _fetch_pending_chunk(CHUNK_SIZE)
        if not chunk:
            break
        result = _run_one_batch(client, chunk)
        n_written += result["n_written"]
        n_theme_rows += result["n_theme_rows"]
        n_failed += result["n_failed"]

    return {"n_pending": n_pending, "n_classified": n_written, "n_theme_rows": n_theme_rows, "n_failed": n_failed}
