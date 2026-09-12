"""Classifies an image (homepage screenshot or ad creative) into the shared
messaging taxonomy using Claude's vision capability.
"""
from __future__ import annotations

import base64
import json
import os

import anthropic

from categorize.attribute_taxonomy import MESSAGE_ATTRIBUTES, MESSAGE_ATTRIBUTE_SYSTEM_PROMPT
from categorize.funnel_taxonomy import FUNNEL_DEFINITIONS, FUNNEL_STAGES
from categorize.messaging_taxonomy import MESSAGING_THEMES

MODEL = "claude-haiku-4-5"

_FUNNEL_SYSTEM_PROMPT = f"""You classify an image (a website homepage screenshot or an ad
creative) from an automotive service, tire, or retail business into exactly one
stage of the See-Think-Do framework, based on what audience intent it targets:

- See: {FUNNEL_DEFINITIONS["See"]}
- Think: {FUNNEL_DEFINITIONS["Think"]}
- Do: {FUNNEL_DEFINITIONS["Do"]}

Reply with ONLY a JSON object: {{"stage": "See" | "Think" | "Do", "confidence": "high|medium|low"}}
No other text."""

_SYSTEM_PROMPT = f"""You classify an image (a website homepage screenshot or an ad
creative) into exactly one theme from this fixed list, based on what it's
visually and textually emphasizing:

{chr(10).join(f"- {t}" for t in MESSAGING_THEMES)}

Reply with ONLY a JSON object: {{"theme": "<one of the exact theme names above>", "confidence": "high|medium|low"}}
No other text."""


def classify_image_theme(image_bytes: bytes, extra_context: str = "") -> tuple:
    """Returns (theme, confidence). Falls back to ("Mixed / Other", "low") on
    any failure so one bad image never crashes a batch run.
    """
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode(),
                },
            },
            {"type": "text", "text": extra_context or "Classify this image."},
        ]
        resp = client.messages.create(
            model=MODEL,
            max_tokens=100,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        raw_text = resp.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            raw_text = raw_text[raw_text.find("{"):raw_text.rfind("}") + 1]
        parsed = json.loads(raw_text)
        theme = parsed["theme"]
        confidence = parsed.get("confidence", "medium")
        if theme not in MESSAGING_THEMES:
            return "Mixed / Other", "low"
        return theme, confidence
    except Exception:  # noqa: BLE001
        return "Mixed / Other", "low"


_AD_HEADLINE_PROMPT = """You are looking at an ad creative (image, banner, or local business
listing card). Extract what it's actually visibly advertising - the headline, offer, and any
specific targeting signal visible in the copy or imagery (e.g. a vehicle make/model, a named
service, a price, a location). This is NOT the advertiser's real bid keyword (that's not
visible in an ad creative) - just describe what the ad itself says and appears to target.

Reply with ONLY a JSON object: {"headline": "short phrase, max ~12 words"}
If the image doesn't show readable ad copy (e.g. it's blank, a generic placeholder, or a video
thumbnail with no text), reply {"headline": null}. No other text, no markdown fences."""


def extract_ad_headline(image_bytes: bytes) -> str | None:
    """Reads the actual visible headline/offer/targeting signal off an ad
    creative image - e.g. "KIA Brake Repair - Save $100" - since Google's Ads
    Transparency data never exposes an advertiser's real bid keyword, the
    ad's own visible copy is the best available signal for what it targets.
    Returns None on any failure or if the image has no readable ad copy."""
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()},
            },
            {"type": "text", "text": "What is this ad's headline/offer/target?"},
        ]
        resp = client.messages.create(
            model=MODEL, max_tokens=60, system=_AD_HEADLINE_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        raw_text = resp.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            raw_text = raw_text[raw_text.find("{"):raw_text.rfind("}") + 1]
        parsed = json.loads(raw_text)
        return parsed.get("headline") or None
    except Exception:  # noqa: BLE001
        return None


def classify_image_funnel_stage(image_bytes: bytes, extra_context: str = "") -> tuple:
    """Returns (stage, confidence) per the See/Think/Do framework. Falls back
    to ("Think", "low") - the middle/default stage - on any failure.
    """
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode(),
                },
            },
            {"type": "text", "text": extra_context or "Classify this image."},
        ]
        resp = client.messages.create(
            model=MODEL,
            max_tokens=80,
            system=_FUNNEL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
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


def classify_image_message_attribute(image_bytes: bytes, extra_context: str = "") -> tuple:
    """Vision counterpart to classify_message_attribute (categorize/classify.py)
    for image-first content (ad creatives, homepage screenshots). Returns
    (attribute, confidence), falling back to ("None Clear / Other", "low").
    """
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode(),
                },
            },
            {"type": "text", "text": extra_context or "Classify this image."},
        ]
        resp = client.messages.create(
            model=MODEL,
            max_tokens=80,
            system=MESSAGE_ATTRIBUTE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        raw_text = resp.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            raw_text = raw_text[raw_text.find("{"):raw_text.rfind("}") + 1]
        parsed = json.loads(raw_text)
        attribute = parsed["attribute"]
        confidence = parsed.get("confidence", "medium")
        if attribute not in MESSAGE_ATTRIBUTES:
            return "None Clear / Other", "low"
        return attribute, confidence
    except Exception:  # noqa: BLE001
        return "None Clear / Other", "low"
