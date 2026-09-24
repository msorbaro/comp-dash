"""Live, single-call summarization of one theme's reviews/mentions - either
the negative complaints or the positive praise - into a couple of
sentences naming the SPECIFIC recurring points. Not a batch job like the
rest of categorize/ (there's no fixed backlog to work through; this runs on
demand for whatever theme/scope/sentiment a page's "what's the complaint?" /
"what's the praise?" control is currently open on). Same live-call pattern
as categorize/classify.py's classify_caption() (single messages.create()
call, not the Batches API - this is a one-off, latency-sensitive request
from a page view, not a bulk pass).
"""
from __future__ import annotations

import os

import anthropic

MODEL = "claude-haiku-4-5"

_FRAMING = {
    "negative": (
        "Summarize the SPECIFIC, concrete recurring COMPLAINTS in 2-3 sentences - name actual "
        'issues (e.g. "quoted one price then charged more at pickup", "appointments not honored, '
        'long waits despite booking ahead"), not generic statements like "customers were unhappy."'
    ),
    "positive": (
        "Summarize the SPECIFIC, concrete recurring PRAISE in 2-3 sentences - name what people "
        'actually valued (e.g. "fixed a slow leak for free while they waited", "technician explained '
        'the repair before doing it"), not generic statements like "customers were happy."'
    ),
}


def _system_prompt(sentiment: str) -> str:
    framing = _FRAMING[sentiment]
    return f"""You read a batch of {sentiment} customer posts/reviews for a car repair/tire
shop, all about ONE specific aspect of the experience (e.g. price, speed, honesty).
{framing} If the posts don't show a clear repeated pattern, say that briefly instead
of inventing one.

Reply with ONLY the summary text - no preamble, no headers, no bullet points, no
quotation marks around the whole thing."""


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def summarize_theme_texts(theme_label: str, texts: list[str], sentiment: str = "negative") -> str | None:
    """Returns a 2-3 sentence summary of the given texts (already filtered
    to one theme + one sentiment by the caller), or None if there's nothing
    to summarize (no texts) or the call fails - a missing summary just means
    the frontend shows nothing extra, not a broken page. `sentiment` is
    'negative' (complaints) or 'positive' (praise) - it only controls the
    prompt framing, the texts themselves are already sentiment-filtered."""
    if not texts:
        return None
    joined = "\n---\n".join(t[:600] for t in texts[:25])
    try:
        resp = _get_client().messages.create(
            model=MODEL, max_tokens=200, system=_system_prompt(sentiment),
            messages=[{"role": "user", "content": f"Theme: {theme_label}\n\nPosts:\n{joined}"}],
        )
        return resp.content[0].text.strip()
    except Exception:  # noqa: BLE001 - a failed summary shouldn't break the page
        return None
