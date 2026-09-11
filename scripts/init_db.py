"""One-time (and safe-to-rerun) setup: creates the schema and seeds
`categories` and `competitors`/`competitor_groups` from config/competitors.yaml.

Run with:  python -m scripts.init_db
"""
import pathlib

import yaml

from categorize.classify import CATEGORIES
from db.connection import get_conn

ROOT = pathlib.Path(__file__).resolve().parent.parent

CATEGORY_DESCRIPTIONS = {
    "Product Feature / New Arrival": "Highlights a specific product or new item, no discount emphasis",
    "Promotion / Sale / Discount": "Price-led: sales, coupons, limited-time offers, BOGO",
    "Educational / How-To / Tips": "Teaches something - usage tips, maintenance advice, explainer content",
    "Behind-the-Scenes / Culture": "Employees, facilities, company culture, day-in-the-life",
    "UGC / Customer Testimonial": "Reposted customer content, reviews, before/after from customers",
    "Holiday / Seasonal": "Tied to a holiday or season, not a specific sale",
    "Community / Cause Marketing": "Charity, sponsorships, local community involvement",
    "Brand / Lifestyle / Awareness": "Brand image content with no direct product or offer",
    "Meme / Trending / Entertainment": "Humor, trends, pop-culture tie-ins",
    "Announcement / News": "Store openings, partnerships, press, leadership news",
    "Contest / Giveaway": "Sweepstakes, giveaways, user-participation contests",
    "Influencer / Partnership Collab": "Content co-created with or featuring an external influencer/partner",
    "Other": "Doesn't clearly fit any category above",
}


def run():
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute((ROOT / "db" / "schema.sql").read_text())

        with conn.cursor() as cur:
            for name in CATEGORIES:
                cur.execute(
                    """INSERT INTO categories (name, description) VALUES (%s, %s)
                       ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description""",
                    (name, CATEGORY_DESCRIPTIONS.get(name, "")),
                )

        competitors = yaml.safe_load((ROOT / "config" / "competitors.yaml").read_text()) or []
        with conn.cursor() as cur:
            for comp in competitors:
                handle = comp["instagram_handle"].lstrip("@").lower()
                cur.execute(
                    """INSERT INTO competitors (name, instagram_handle, instagram_url, website_url,
                                                 facebook_url, is_own_brand, notes)
                       VALUES (%(name)s, %(handle)s, %(url)s, %(website_url)s, %(facebook_url)s,
                               %(is_own_brand)s, %(notes)s)
                       ON CONFLICT (instagram_handle) DO UPDATE
                           SET name = EXCLUDED.name, website_url = EXCLUDED.website_url,
                               facebook_url = EXCLUDED.facebook_url,
                               is_own_brand = EXCLUDED.is_own_brand, notes = EXCLUDED.notes
                       RETURNING id""",
                    {
                        "name": comp["name"],
                        "handle": handle,
                        "url": comp.get("instagram_url") or f"https://instagram.com/{handle}",
                        "website_url": comp.get("website_url"),
                        # Best-guess default: most brands use the same slug as their IG handle.
                        # Not independently verified per-company - the ads scraper flags any
                        # page URL that returns no results so wrong guesses surface naturally.
                        "facebook_url": comp.get("facebook_url") or f"https://www.facebook.com/{handle}",
                        "is_own_brand": bool(comp.get("is_own_brand", False)),
                        "notes": comp.get("notes"),
                    },
                )
                competitor_id = cur.fetchone()[0]
                cur.execute("DELETE FROM competitor_groups WHERE competitor_id = %s", (competitor_id,))
                for group in comp.get("groups", []):
                    cur.execute(
                        "INSERT INTO competitor_groups (competitor_id, group_name) VALUES (%s, %s)",
                        (competitor_id, group),
                    )

    print(f"Seeded {len(CATEGORIES)} categories and {len(competitors)} competitors.")


if __name__ == "__main__":
    run()
