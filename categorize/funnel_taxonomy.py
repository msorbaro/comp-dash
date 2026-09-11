"""See-Think-Do framework (Avinash Kaushik), adapted for the auto/tire/service
retail segment this project tracks. Used to classify every piece of content
(social posts, ads, homepage screenshots) by which audience intent it targets.
"""

FUNNEL_STAGES = ["See", "Think", "Do"]

FUNNEL_DEFINITIONS = {
    "See": (
        "Broadest possible audience, no commercial intent yet - people who might "
        "someday need a tire/oil change/brake job but aren't thinking about it right "
        "now. Content here is entertaining, aspirational, or culturally relevant: "
        "brand personality, humor/memes, holiday greetings, community involvement, "
        "employee spotlights, general car-care lifestyle content. The goal is "
        "reach and likability, not a specific action."
    ),
    "Think": (
        "Audience is aware they may have a need and is evaluating - weak commercial "
        "intent. Content here educates or differentiates: 'signs you need new brakes,' "
        "why tire rotation matters, what makes this shop's technicians/warranty/"
        "locations better, general service or product features explained without a "
        "hard price push. Helps someone move from 'I might need this' to 'here's who "
        "I'd consider.'"
    ),
    "Do": (
        "Strong commercial intent - audience is ready to act now. Content here is "
        "conversion-focused: specific prices, % off, coupons, limited-time offers, "
        "'book now'/'visit today' calls to action, contests/giveaways requiring "
        "immediate action. The goal is to get someone into the shop or onto the "
        "site this week."
    ),
}

FUNNEL_SYSTEM_PROMPT = f"""You classify a single piece of marketing content from an
automotive service, tire, or retail business into exactly one stage of the
See-Think-Do framework, based on what audience intent it appears designed to target:

- See: {FUNNEL_DEFINITIONS["See"]}
- Think: {FUNNEL_DEFINITIONS["Think"]}
- Do: {FUNNEL_DEFINITIONS["Do"]}

Reply with ONLY a JSON object: {{"stage": "See" | "Think" | "Do", "confidence": "high|medium|low"}}
No other text."""
