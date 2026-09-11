"""Shared "what is this trying to sell" taxonomy, used for both homepage
screenshots and ad creatives (they're the same underlying question - deals vs.
product vs. lifestyle vs. something else - so one shared taxonomy keeps the
dashboard's language consistent across the two).
"""

MESSAGING_THEMES = [
    "Deals / Promotional",
    "Product-Led",
    "Lifestyle / Brand Imagery",
    "Seasonal / Holiday",
    "Announcement / Launch",
    "Testimonial / Social Proof",
    "Recruitment / Hiring",
    "Mixed / Other",
]

MESSAGING_THEME_DESCRIPTIONS = {
    "Deals / Promotional": "Price-led: % off, sales, coupons, limited-time offers dominate the page",
    "Product-Led": "A specific product or product category is the visual/textual focus, no discount emphasis",
    "Lifestyle / Brand Imagery": "Aspirational lifestyle photography or mood/brand imagery, not a specific product or price",
    "Seasonal / Holiday": "Built around a holiday or season (not just a seasonal sale)",
    "Announcement / Launch": "New product launch, store opening, partnership, or other news",
    "Testimonial / Social Proof": "Customer reviews, ratings, UGC, or 'as seen in' proof points are the focus",
    "Recruitment / Hiring": "Hiring/careers messaging is the dominant content",
    "Mixed / Other": "No single theme dominates, or doesn't fit the above",
}
