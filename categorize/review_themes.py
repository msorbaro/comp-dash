"""Multi-label theme extraction for voice.reviews, via the Message Batches
API (same 50%-off, bulk-non-latency-sensitive rationale as
categorize/sentiment.py, which this module runs independently of - a
review's overall sentiment and its per-theme breakdown are separate passes,
separately retryable).

Unlike overall sentiment (one label per review), a review routinely touches
several distinct aspects with DIFFERENT sentiment each - "fast service but
overpriced" is positive on speed, negative on price. So each review gets 0-3
(theme, sentiment) pairs, written to voice.review_themes (a many-to-one
companion table, not columns on voice.reviews itself).

Themes are a FIXED taxonomy (THEMES below), not free text the model invents
per review - a per-review free-text theme would fragment into thousands of
near-duplicate strings and be useless for aggregation/charting. The taxonomy
was chosen from domain knowledge of tire/auto-repair reviews specifically
(not a generic "customer service" template) - see THEMES for the full list
and what each one covers.
"""
from __future__ import annotations

import json
import os
import time

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from db.connection import get_conn

MODEL = "claude-haiku-4-5"
CHUNK_SIZE = 12_000
WRITE_COMMIT_BATCH = 500  # commit every N reviews written - see _run_one_batch's write loop
POLL_SECONDS = 20

# (theme key, short description shown to the model). Order here is the
# order shown in the prompt, not meaningful otherwise.
THEMES = [
    ("price_value", "cost, pricing, fees, deals, discounts, value for money"),
    ("speed_wait_time", "how fast or slow the service/repair was, wait times, being kept waiting"),
    ("customer_service", "staff friendliness, courtesy, attitude, how customers were treated"),
    ("technical_quality", "quality/correctness of the actual repair work, technician skill and competence"),
    ("honesty_trust", "honesty, transparency, feeling scammed/ripped off/lied to, trustworthiness"),
    ("upselling_pressure", "pushy sales tactics, being pressured into unnecessary work or add-ons"),
    ("convenience_location", "location convenience, hours, accessibility, ease of getting there"),
    ("scheduling_ease", "booking appointments, walk-in availability, getting in quickly"),
    ("communication", "being kept informed, clear explanations of the problem/work/cost, follow-up calls"),
    ("cleanliness_facility", "cleanliness/comfort of the shop, waiting area, restrooms"),
    ("warranty_followup", "warranty being honored, guarantees, after-the-fact support if something goes wrong"),
    ("product_selection", "availability/selection of tire brands or parts in stock"),
    ("other", "a real, substantive theme that doesn't fit any category above"),
]
THEME_KEYS = {t[0] for t in THEMES}
_THEME_LIST_TEXT = "\n".join(f'- "{k}": {desc}' for k, desc in THEMES)

SYSTEM_PROMPT = f"""You read a single Google review (star rating + text) for a car repair/tire shop and identify which specific aspects of the experience it actually discusses, with the sentiment toward EACH aspect separately - a review can be positive about one thing and negative about another (e.g. "fast service but overpriced" is positive on speed, negative on price).

Pick 1-3 of the most salient themes actually discussed below - not every theme that could theoretically apply, just what this specific review is really about. Only return an empty list if the review has no substantive content to theme (e.g. just "Good." or a rating with no real detail).

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
            cur.execute("SELECT count(*) FROM voice.reviews WHERE themed_at IS NULL AND text IS NOT NULL AND text != ''")
            return cur.fetchone()[0]


def _fetch_pending_chunk(limit: int) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT review_id, rating, text FROM voice.reviews
                   WHERE themed_at IS NULL AND text IS NOT NULL AND text != '' LIMIT %s""",
                (limit,),
            )
            rows = cur.fetchall()
    return [{"review_id": r, "rating": rating, "text": text} for r, rating, text in rows]


def _fetch_random_sample(n: int) -> list[dict]:
    """A genuinely random cross-section (any brand, any month) rather than
    whatever `LIMIT` happens to return first - for validating theme quality
    on a small slice before committing to the full backlog."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT review_id, rating, text FROM voice.reviews
                   WHERE themed_at IS NULL AND text IS NOT NULL AND text != ''
                   ORDER BY random() LIMIT %s""",
                (n,),
            )
            rows = cur.fetchall()
    return [{"review_id": r, "rating": rating, "text": text} for r, rating, text in rows]


def _run_one_batch(client: anthropic.Anthropic, rows: list[dict]) -> dict:
    requests = [
        Request(
            custom_id=str(r["review_id"]),
            params=MessageCreateParamsNonStreaming(
                model=MODEL, max_tokens=250, system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"Star rating: {r['rating']}\nReview text: {r['text']}",
                }],
            ),
        )
        for r in rows
    ]
    batch = client.messages.batches.create(requests=requests)
    print(f"Created batch {batch.id} ({len(requests)} reviews)", flush=True)

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

    # Parse everything into memory first, write in a separate connection
    # after - same lesson as categorize/sentiment.py's _run_one_batch (a
    # connection held open across this whole paginated results iteration
    # can idle out and get killed server-side on a large batch).
    parsed: dict[int, list[dict]] = {}
    n_failed = 0
    for result in client.messages.batches.results(batch.id):
        review_id = int(result.custom_id)
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
        except Exception:  # noqa: BLE001 - one bad response shouldn't crash the batch write
            n_failed += 1
            continue
        parsed[review_id] = themes[:3]

    # Commit every WRITE_COMMIT_BATCH reviews rather than one giant
    # transaction - same statement-timeout lesson as categorize/sentiment.py.
    n_written, n_theme_rows = 0, 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for review_id, themes in parsed.items():
                # DELETE + re-INSERT (not upsert) since a re-run legitimately
                # changes the theme SET, not just individual rows' fields.
                cur.execute("DELETE FROM voice.review_themes WHERE review_id = %s", (review_id,))
                for t in themes:
                    cur.execute(
                        """INSERT INTO voice.review_themes (review_id, theme, theme_sentiment)
                           VALUES (%s, %s, %s) ON CONFLICT (review_id, theme) DO NOTHING""",
                        (review_id, t["theme"], t["sentiment"]),
                    )
                    n_theme_rows += 1
                cur.execute("UPDATE voice.reviews SET themed_at = now() WHERE review_id = %s", (review_id,))
                n_written += 1
                if n_written % WRITE_COMMIT_BATCH == 0:
                    conn.commit()
        conn.commit()
    finally:
        conn.close()

    return {"n_written": n_written, "n_theme_rows": n_theme_rows, "n_failed": n_failed}


def classify_pending() -> dict:
    """Themes every voice.reviews row with themed_at still NULL (and real
    text), walking the backlog in CHUNK_SIZE-row slices."""
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


def sample_classify(n: int = 600) -> dict:
    """Themes a random cross-section of `n` reviews (not the whole backlog)
    and reports a frequency/example breakdown - for validating theme
    quality before committing to the full run. Writes real results (not
    thrown away), so a later classify_pending() picks up from here rather
    than redoing this work."""
    client = _get_client()
    rows = _fetch_random_sample(n)
    if not rows:
        return {"n_sampled": 0, "themes": {}}
    result = _run_one_batch(client, rows)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT rt.theme, rt.theme_sentiment, count(*)
                   FROM voice.review_themes rt
                   WHERE rt.review_id = ANY(%s)
                   GROUP BY rt.theme, rt.theme_sentiment
                   ORDER BY rt.theme""",
                ([r["review_id"] for r in rows],),
            )
            counts = cur.fetchall()

            cur.execute(
                """SELECT rt.theme, rt.theme_sentiment, r.text, r.rating
                   FROM voice.review_themes rt JOIN voice.reviews r ON r.review_id = rt.review_id
                   WHERE rt.review_id = ANY(%s)
                   ORDER BY rt.theme, random()""",
                ([r["review_id"] for r in rows],),
            )
            examples_raw = cur.fetchall()

    themes: dict = {}
    for theme, sentiment, n in counts:
        bucket = themes.setdefault(theme, {"positive": 0, "neutral": 0, "negative": 0, "examples": []})
        bucket[sentiment] = n
    for theme, sentiment, text, rating in examples_raw:
        bucket = themes[theme]
        if len(bucket["examples"]) < 3:
            bucket["examples"].append({"sentiment": sentiment, "rating": rating, "text": text})

    return {
        "n_sampled": len(rows), "n_failed": result["n_failed"],
        "n_theme_rows": result["n_theme_rows"], "themes": themes,
    }
