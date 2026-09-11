"""Classifies an image (homepage screenshot or ad creative) into the shared
messaging taxonomy using Claude's vision capability.
"""
from __future__ import annotations

import base64
import json
import os

import anthropic

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
