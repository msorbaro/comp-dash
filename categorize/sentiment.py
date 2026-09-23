"""Sentiment classification for voice.reviews, via the Message Batches API
(50% off standard pricing - appropriate here since this is a bulk, non-
latency-sensitive pass, unlike the live classify_caption()/classify_funnel_stage()
calls in categorize/classify.py, which this module otherwise mirrors: same
model, same compact-JSON-only prompting style.

Reviews with a star rating but no text get a cheap rule-based label instead
of an LLM call - there's no "what was said" to analyze, and inferring
positive/neutral/negative straight from the star count is unambiguous, so
paying for a classification call there would be pure waste.
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
BATCH_MAX_REQUESTS = 100_000  # the Batches API's own hard cap per batch
# Local chunk size, well under the API cap above - keeps peak memory low
# when building the Request list (58k pending rows OOM-killed a run on a
# memory-constrained machine; each Request object plus its copy of the
# review text and system prompt adds up fast at that count).
CHUNK_SIZE = 12_000
WRITE_COMMIT_BATCH = 500  # commit every N UPDATEs - see _run_one_batch's write loop
POLL_SECONDS = 20

SYSTEM_PROMPT = """You read a single Google review (star rating + text) for a car repair/tire shop and label its sentiment.
Judge the TEXT primarily - a low star rating with a text that's actually complimentary (e.g. "so far so good, ask me again in a year") should be judged on what's actually said, not just the number.

Reply with ONLY a JSON object:
{"sentiment": "positive|neutral|negative", "confidence": "high|medium|low", "reason": "<5-12 words on what drove the label>"}
No other text."""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _rating_only_sentiment(rating: int | None) -> str | None:
    if rating is None:
        return None
    if rating >= 4:
        return "positive"
    if rating == 3:
        return "neutral"
    return "negative"


def _count_pending() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM voice.reviews WHERE sentiment IS NULL")
            return cur.fetchone()[0]


def _fetch_pending_chunk(limit: int) -> list[dict]:
    """One bounded slice of pending rows, not the whole backlog - each
    already-classified row drops out of `WHERE sentiment IS NULL`, so
    repeated calls naturally walk the full backlog without ever holding
    more than `limit` rows (and their review text) in memory at once."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT review_id, rating, text FROM voice.reviews
                   WHERE sentiment IS NULL LIMIT %s""",
                (limit,),
            )
            rows = cur.fetchall()
    return [{"review_id": r, "rating": rating, "text": text} for r, rating, text in rows]


def _write_rating_only(rows: list[dict]) -> int:
    if not rows:
        return 0
    with get_conn() as conn:
        with conn:
            with conn.cursor() as cur:
                for r in rows:
                    cur.execute(
                        """UPDATE voice.reviews
                           SET sentiment = %(sentiment)s, sentiment_confidence = 'low',
                               sentiment_reason = 'rating only, no review text'
                           WHERE review_id = %(review_id)s""",
                        {"sentiment": _rating_only_sentiment(r["rating"]), "review_id": r["review_id"]},
                    )
    return len(rows)


def _run_one_batch(client: anthropic.Anthropic, rows: list[dict]) -> dict:
    requests = [
        Request(
            custom_id=str(r["review_id"]),
            params=MessageCreateParamsNonStreaming(
                model=MODEL, max_tokens=100, system=SYSTEM_PROMPT,
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

    # Parse every result from Anthropic FIRST, into plain memory - no DB
    # connection held open here. client.messages.batches.results() makes
    # its own paginated calls to Anthropic as it iterates, which for ~10k
    # results can take long enough that a DB connection held open the
    # whole time idles out and gets killed server-side (confirmed live -
    # a real run died mid-write this way). Same lesson voice/places.py's
    # own comments already document for a different long-running call.
    parsed_updates = []
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
            parsed = json.loads(text)
            sentiment = parsed["sentiment"]
            if sentiment not in ("positive", "neutral", "negative"):
                raise ValueError(sentiment)
        except Exception:  # noqa: BLE001 - one bad response shouldn't crash the batch write
            n_failed += 1
            continue
        parsed_updates.append({
            "sentiment": sentiment, "confidence": parsed.get("confidence", "medium"),
            "reason": parsed.get("reason", ""), "review_id": review_id,
        })

    # Write everything in one connection, but commit every WRITE_COMMIT_BATCH
    # rows rather than as one giant transaction - a single transaction of
    # 10k+ sequential UPDATEs hit Supabase's statement timeout and rolled
    # back the entire thing, confirmed live (lost an already-completed
    # batch's results this way). Periodic commits mean a timeout or crash
    # partway through only loses the rows since the last commit, not
    # everything.
    n_written = 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for u in parsed_updates:
                cur.execute(
                    """UPDATE voice.reviews
                       SET sentiment = %(sentiment)s, sentiment_confidence = %(confidence)s,
                           sentiment_reason = %(reason)s
                       WHERE review_id = %(review_id)s""",
                    u,
                )
                n_written += 1
                if n_written % WRITE_COMMIT_BATCH == 0:
                    conn.commit()
        conn.commit()
    finally:
        conn.close()

    return {"n_written": n_written, "n_failed": n_failed}


def classify_pending() -> dict:
    """Classifies every voice.reviews row with sentiment still NULL, walking
    the backlog in CHUNK_SIZE-row slices (never loading the whole backlog's
    review text into memory at once - a live run on a memory-constrained
    machine got OOM-killed doing that at ~58k pending rows)."""
    n_pending = _count_pending()
    client = _get_client()
    n_rating_only, n_written, n_failed = 0, 0, 0

    while True:
        chunk = _fetch_pending_chunk(CHUNK_SIZE)
        if not chunk:
            break
        text_rows = [r for r in chunk if r["text"]]
        rating_only_rows = [r for r in chunk if not r["text"]]

        n_rating_only += _write_rating_only(rating_only_rows)
        if text_rows:
            result = _run_one_batch(client, text_rows)
            n_written += result["n_written"]
            n_failed += result["n_failed"]

    return {
        "n_pending": n_pending, "n_rating_only": n_rating_only,
        "n_llm_classified": n_written, "n_llm_failed": n_failed,
    }
