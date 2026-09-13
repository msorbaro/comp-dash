"""Claude-based synthesis for the Brand/Channel pages: what a brand is
actually saying at each See/Think/Do stage on a given channel (not just a
couple of raw example captions), a richer interpretive "Read:" line, and
(separately) a brand's tagline + positioning for the brand header.

Every call here is TTL-cached in-process - these are real LLM calls with
real latency/cost, and the underlying data only changes on the weekly
scrape, so a long cache (hours) is the right tradeoff, not a 10-minute one.
"""
import functools
import json
import os
import time

import anthropic

MODEL = "claude-haiku-4-5"
CACHE_TTL = 6 * 3600  # 6 hours
_cache: dict = {}
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _cached(key, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit and now < hit[1]:
        return hit[0]
    value = fn()
    _cache[key] = (value, now + CACHE_TTL)
    return value


def _extract_json(raw_text: str) -> dict:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
    raw_text = raw_text[raw_text.find("{"):raw_text.rfind("}") + 1]
    return json.loads(raw_text)


CHANNEL_SYNTHESIS_PROMPT = """You are a marketing analyst. You'll see real example captions/ad
copy a brand posted on ONE channel, grouped by See/Think/Do funnel stage:
- See: broad-awareness content for people who may not be in-market yet.
- Think: content for people considering options / learning about the product or service.
- Do: content for people ready to act now (offers, promotions, calls to action).

For each stage, write ONE concise sentence synthesizing the ACTUAL recurring theme - name
specific offers, prices, topics, or hooks if they recur across the examples. Do not write
generic filler like "promotes the brand". If a stage has zero examples, respond for it with
exactly: "No content classified in this stage yet."

Then write one more sentence - "read_line" - a more interpretive read of this channel's
overall approach: not just restating the percentages, but what the pattern actually means
(e.g. specific recurring offers, whether it reads as brand-building or purely transactional,
anything distinctive).

Note on Paid Search examples specifically: they may read as "AdvertiserName — bidding on
'term'". The advertiser name shown is this brand's own registered Google Ads account, which
is sometimes a parent/corporate entity rather than the storefront brand name (e.g. a
franchise's corporate owner buying the ads) - it is NOT a different, rival company. Never
describe these as "competitor hijacking" or "intercepting a competitor's customers" - it is
this brand's own ad spend, most often defending or promoting its own branded search term.

Reply with ONLY a JSON object: {"see": "...", "think": "...", "do": "...", "read_line": "..."}
No other text, no markdown fences."""


def channel_synthesis(brand: str, channel_name: str, dominant_pct: int, dominant_stage: str,
                       examples_by_stage: dict) -> dict:
    """examples_by_stage: {"See": [str, ...], "Think": [...], "Do": [...]} - real captions,
    already reasonably truncated by the caller."""
    key = ("channel_synthesis", brand, channel_name, tuple(
        tuple(examples_by_stage.get(s, [])) for s in ("See", "Think", "Do")
    ))

    def _call():
        fallback = {
            "see": _fallback_line(examples_by_stage.get("See")),
            "think": _fallback_line(examples_by_stage.get("Think")),
            "do": _fallback_line(examples_by_stage.get("Do")),
            "read_line": f"{dominant_pct}% {dominant_stage}.",
        }
        if not any(examples_by_stage.values()):
            return fallback
        user_content = f"Brand: {brand}\nChannel: {channel_name}\n\n" + "\n\n".join(
            f"{stage} examples:\n" + "\n".join(f"- {t}" for t in texts[:15])
            for stage, texts in examples_by_stage.items() if texts
        )
        try:
            resp = _get_client().messages.create(
                model=MODEL, max_tokens=400, system=CHANNEL_SYNTHESIS_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            parsed = _extract_json(resp.content[0].text)
            return {
                "see": parsed.get("see") or fallback["see"],
                "think": parsed.get("think") or fallback["think"],
                "do": parsed.get("do") or fallback["do"],
                "read_line": parsed.get("read_line") or fallback["read_line"],
            }
        except Exception:  # noqa: BLE001
            return fallback

    return _cached(key, _call)


def _fallback_line(examples) -> str:
    return "No content classified in this stage yet." if not examples else examples[0][:100]


POSITIONING_PROMPT = """You are a brand strategist. You'll see a company name and a sample of
its real marketing copy across channels (social captions, ad headlines, website copy) posted
in the LAST 6 MONTHS ONLY.

1. "tagline": if you are confident this company has a real, publicly-used tagline or slogan,
   state it exactly - this can draw on general knowledge of the company, not just the sample.
   If you are not confident (e.g. a small regional chain with no famous slogan you actually
   know), respond null - never invent one.
2. "positioning": 2-3 sentences answering "what has this brand actually been telling its
   customers in the last 6 months" - based ONLY on the sample shown, not general knowledge or
   older history. Name the concrete, recurring themes (specific offers, topics, tone), not
   generic guesses. If the sample is thin, say so plainly rather than overreaching.

Reply with ONLY a JSON object: {"tagline": "..." or null, "positioning": "..."}
No other text, no markdown fences."""


def brand_positioning(brand: str, sample_texts: list) -> dict:
    key = ("brand_positioning", brand, tuple(sample_texts))

    def _call():
        fallback = {"tagline": None, "positioning": None}
        if not sample_texts:
            return fallback
        user_content = f"Company: {brand}\n\nSample marketing copy:\n" + "\n".join(
            f"- {t}" for t in sample_texts[:40]
        )
        try:
            resp = _get_client().messages.create(
                model=MODEL, max_tokens=300, system=POSITIONING_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            parsed = _extract_json(resp.content[0].text)
            return {"tagline": parsed.get("tagline"), "positioning": parsed.get("positioning")}
        except Exception:  # noqa: BLE001
            return fallback

    return _cached(key, _call)


CATEGORY_CHANNEL_THEMES_PROMPT = """You are a marketing analyst looking at real captions/ad
copy from MANY DIFFERENT companies in the same competitive category, all on the same one
marketing channel. Identify 3-6 recurring THEMES that show up across multiple different
companies - patterns general enough to apply across brands, not one company's specific offer.

A theme can be either:
- a messaging theme (what it's about): e.g. "Seasonal/holiday tie-ins", "Percent-off deals",
  "Educational how-to content", "New location announcements", "Employee/team spotlights"
- a content style/format (how it's made): e.g. "Influencer-led", "Cartoon/animated",
  "User-generated content", "Testimonial/review-driven", "Produced video with a host"

Rules:
- NEVER include a specific brand name, dollar amount, or company-specific detail - a theme
  must read the same way regardless of which company in the category you're looking at.
- Each theme is a short label, 2-5 words.
- Only include a theme if you can see it recurring across more than one company's examples -
  a single company's one-off isn't a category theme.
- If the examples are too thin or too similar to find real cross-brand patterns, return fewer
  themes rather than inventing ones you don't see.

Reply with ONLY a JSON object: {"themes": ["...", "...", ...]}
No other text, no markdown fences."""


def category_channel_themes(category_name: str, channel_name: str, sample_texts: list) -> list:
    """Generalized, cross-brand recurring themes for one channel within a
    category - e.g. "Seasonal references", "Percent-off deals", "Meme
    format" - deliberately generic enough to apply to any brand in the
    category, unlike a brand's own specific captions."""
    key = ("category_channel_themes", category_name, channel_name, tuple(sample_texts))

    def _call():
        if not sample_texts:
            return []
        user_content = f"Category: {category_name}\nChannel: {channel_name}\n\n" + "\n".join(
            f"- {t}" for t in sample_texts[:60]
        )
        try:
            resp = _get_client().messages.create(
                model=MODEL, max_tokens=250, system=CATEGORY_CHANNEL_THEMES_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            parsed = _extract_json(resp.content[0].text)
            themes = parsed.get("themes") or []
            return [t for t in themes if isinstance(t, str) and t.strip()][:6]
        except Exception:  # noqa: BLE001
            return []

    return _cached(key, _call)
