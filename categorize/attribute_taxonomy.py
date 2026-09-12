"""Fixed "what value proposition is this actually leaning on" taxonomy - a
permanent, classifiable dimension so questions like "how much of our See
content talks about Safety vs. the market" can be answered with a real count
against real classified data, not an AI guess from a sample each time the
page loads. Mirrors the existing funnel_stage/category pattern (same fixed
list, same one-attribute-per-post design) rather than inventing a new one.

This is orthogonal to funnel stage (WHO it's for: See/Think/Do) and content
category (WHAT FORMAT it is: promo/testimonial/etc) - it's the underlying
ATTRIBUTE being sold: why should this brand win, in this one piece of
content's own terms.
"""

MESSAGE_ATTRIBUTES = [
    "Safety & Protection",
    "Trust & Reliability",
    "Price & Value",
    "Convenience & Speed",
    "Expertise & Professionalism",
    "Local & Community",
    "Quality & Craftsmanship",
    "Emotional & Lifestyle",
    "Social Proof & Reputation",
    "None Clear / Other",
]

MESSAGE_ATTRIBUTE_DESCRIPTIONS = {
    "Safety & Protection": "Keeping people/family/vehicle safe, avoiding breakdowns or accidents, peace of mind about physical risk",
    "Trust & Reliability": "Dependability, consistency, 'you can count on us', being a long-standing/established name",
    "Price & Value": "Savings, affordability, discounts, price comparisons, getting more for less",
    "Convenience & Speed": "Fast, easy, no appointment needed, one-stop-shop, minimal effort or wait",
    "Expertise & Professionalism": "Certified technicians, specialized knowledge, credentials, doing the job right",
    "Local & Community": "Neighborhood ties, local ownership, community involvement, sponsorships, 'we're your neighbors'",
    "Quality & Craftsmanship": "Premium materials, durability, attention to detail, superior workmanship",
    "Emotional & Lifestyle": "Humor, personality, relatable life moments, aspirational imagery - not a functional claim",
    "Social Proof & Reputation": "Reviews, ratings, awards, 'as seen in', customer testimonials as the credibility lever",
    "None Clear / Other": "No single attribute dominates, or the content doesn't make a value-proposition claim at all",
}

MESSAGE_ATTRIBUTE_SYSTEM_PROMPT = f"""You classify a single piece of marketing content from an
automotive service, tire, or retail business into exactly one MESSAGE ATTRIBUTE - the underlying
value proposition it's leaning on to win the customer, from this fixed list:

{chr(10).join(f"- {a}: {d}" for a, d in MESSAGE_ATTRIBUTE_DESCRIPTIONS.items())}

This is different from what FORMAT the content is (a promo, a testimonial, a meme) - it's WHY
the content thinks the brand deserves the customer. Pick the single attribute that's most
clearly the point of this specific piece of content, not a generic guess.

Reply with ONLY a JSON object: {{"attribute": "<one of the exact names above>", "confidence": "high|medium|low"}}
No other text."""
