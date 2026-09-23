"""Relevance + sentiment + theme classification for voice.reddit_mentions,
via the Message Batches API (50% off, same bulk-non-latency-sensitive
rationale as categorize/sentiment.py).

Unlike a Google/Yelp review, a Reddit search hit is NOT guaranteed to
actually be about the brand - confirmed live in the Mavis test, where ~10%
of relevance-sorted results were false positives (an unrelated r/AskReddit
post, a rental-car complaint that just happened to mention the word). So
relevance is classified FIRST, in the same call as sentiment/theme - one
combined Haiku call per item rather than two passes, since running a
separate relevance-only pass first would double the round trips for a
marginal token savings on the ~10% that get dropped.
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
CHUNK_SIZE = 5_000
WRITE_COMMIT_BATCH = 500  # commit every N UPDATEs - see _run_one_batch's write loop
POLL_SECONDS = 20

THEMES = ["complaint", "question", "recommendation", "price_or_deal", "comparison", "employment", "news", "other"]

SYSTEM_PROMPT = f"""You read a single Reddit post or comment that turned up in a keyword search for one specific auto repair/tire brand ("{{brand}}"). Reddit search returns false positives - unrelated content that just happens to contain the word, or a different meaning of the same word/name entirely. Judge relevance first.

For a big-box retailer's automotive department specifically (Walmart Auto Care Center, Sam's Club Tire & Battery, Costco Tire Center) - mark is_relevant=false for posts about the parent store in general (shopping, prices, membership, employment elsewhere in the store, corporate news) even though they mention the same company name. Only mark relevant if the post is actually about the tire/auto service department.

Reply with ONLY a JSON object:
{{"is_relevant": true|false, "sentiment": "positive|neutral|negative"|null, "theme": "{'|'.join(THEMES)}"|null, "comparison_brand": "<name of the OTHER brand being compared, if theme=comparison, else null>", "reason": "<5-12 words>"}}
sentiment/theme/comparison_brand MUST be null when is_relevant is false. No other text."""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _count_pending() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM voice.reddit_mentions WHERE is_relevant IS NULL")
            return cur.fetchone()[0]


def _fetch_pending_chunk(limit: int) -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT rm.mention_id, vb.name, rm.title, rm.text
                   FROM voice.reddit_mentions rm JOIN voice.brands vb ON vb.brand_id = rm.brand_id
                   WHERE rm.is_relevant IS NULL LIMIT %s""",
                (limit,),
            )
            rows = cur.fetchall()
    return [{"mention_id": r, "brand_name": name, "title": title, "text": text} for r, name, title, text in rows]


def _brand_id_by_name() -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT brand_id, name FROM voice.brands")
            return {name.lower(): bid for bid, name in cur.fetchall()}


def _run_one_batch(client: anthropic.Anthropic, rows: list, brand_ids_by_name: dict) -> dict:
    requests = []
    for r in rows:
        content = f"Title: {r['title'] or '(none - this is a comment)'}\nText: {r['text'] or '(no text)'}"
        requests.append(Request(
            custom_id=str(r["mention_id"]),
            params=MessageCreateParamsNonStreaming(
                model=MODEL, max_tokens=120,
                system=SYSTEM_PROMPT.replace("{brand}", r["brand_name"]),
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

    # Parse every result from Anthropic FIRST, into plain memory - no DB
    # connection held open here. See categorize/sentiment.py's
    # _run_one_batch for why: a DB connection held open across this whole
    # (paginated, Anthropic-side) iteration can idle out and get killed
    # server-side on a large batch - confirmed live on the review pipeline.
    parsed_updates = []
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
            parsed = json.loads(text)
            is_relevant = bool(parsed["is_relevant"])
            sentiment = parsed.get("sentiment") if is_relevant else None
            theme = parsed.get("theme") if is_relevant else None
            if sentiment is not None and sentiment not in ("positive", "neutral", "negative"):
                sentiment = None
            if theme is not None and theme not in THEMES:
                theme = None
        except Exception:  # noqa: BLE001 - one bad response shouldn't crash the batch write
            n_failed += 1
            continue
        comparison_brand_id = None
        comparison_name = (parsed.get("comparison_brand") or "").strip().lower()
        if comparison_name:
            comparison_brand_id = brand_ids_by_name.get(comparison_name)
        parsed_updates.append({
            "is_relevant": is_relevant, "sentiment": sentiment, "theme": theme,
            "comparison_brand_id": comparison_brand_id, "reason": parsed.get("reason", ""),
            "mention_id": mention_id,
        })

    # Commit every WRITE_COMMIT_BATCH rows rather than as one giant
    # transaction - see categorize/sentiment.py's _run_one_batch for why
    # (a 10k+-row single transaction hit Supabase's statement timeout and
    # rolled back an already-completed batch's results, live).
    n_written = 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for u in parsed_updates:
                cur.execute(
                    """UPDATE voice.reddit_mentions
                       SET is_relevant = %(is_relevant)s, sentiment = %(sentiment)s, theme = %(theme)s,
                           comparison_brand_id = %(comparison_brand_id)s, reason = %(reason)s
                       WHERE mention_id = %(mention_id)s""",
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
    """Classifies every voice.reddit_mentions row with is_relevant still
    NULL, walking the backlog in CHUNK_SIZE-row slices (same memory
    discipline as categorize/sentiment.py)."""
    n_pending = _count_pending()
    client = _get_client()
    brand_ids_by_name = _brand_id_by_name()
    n_written, n_failed = 0, 0

    while True:
        chunk = _fetch_pending_chunk(CHUNK_SIZE)
        if not chunk:
            break
        result = _run_one_batch(client, chunk, brand_ids_by_name)
        n_written += result["n_written"]
        n_failed += result["n_failed"]

    return {"n_pending": n_pending, "n_classified": n_written, "n_failed": n_failed}
