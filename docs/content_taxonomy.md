---
title: Content Category Taxonomy
status: draft — auto-applied by default, editable any time
---

# Content Category Taxonomy

Every scraped post gets tagged with exactly one **primary category** below (an LLM reads the caption + image and picks the best fit at ingest time). You can rename, merge, split, or manually override categories at any time — this list lives here in plain markdown and in the `categories` table in the database so it's never just "in the chat."

| Category | Definition | Example |
|---|---|---|
| Product Feature / New Arrival | Highlights a specific product or new item, no discount emphasis | "New fall collection just dropped" |
| Promotion / Sale / Discount | Price-led: sales, coupons, limited-time offers, BOGO | "20% off this weekend only" |
| Educational / How-To / Tips | Teaches something — usage tips, maintenance advice, explainer content | "3 signs your AC needs service" |
| Behind-the-Scenes / Culture | Employees, facilities, company culture, "day in the life" | Staff spotlight, warehouse tour |
| UGC / Customer Testimonial | Reposted customer content, reviews, before/after from customers | Customer photo repost |
| Holiday / Seasonal | Tied to a holiday or season, not a specific sale | July 4th graphic, winter prep reminder |
| Community / Cause Marketing | Charity, sponsorships, local community involvement | Donation drive, sponsorship post |
| Brand / Lifestyle / Awareness | Brand image content with no direct product or offer | Mood/aesthetic brand video |
| Meme / Trending / Entertainment | Humor, trends, pop-culture tie-ins | Meme format, trending audio Reel |
| Announcement / News | Store openings, partnerships, press, leadership news | "Now open in Austin!" |
| Contest / Giveaway | Sweepstakes, giveaways, user-participation contests | "Tag a friend to win" |
| Influencer / Partnership Collab | Content co-created with or featuring an external influencer/partner | Influencer unboxing |
| Other | Doesn't clearly fit any category above | Catch-all fallback |

**Secondary attributes tracked separately from category** (not mutually exclusive with the above):
- **Format**: Image, Carousel, Reel/Video
- Note: Instagram **Stories** are excluded from scope — they expire after 24h and aren't accessible for accounts we don't manage. Only permanent feed posts and Reels are tracked.

## How categorization works
1. New post scraped → caption + first image/thumbnail sent to Claude with this taxonomy.
2. Claude returns the single best-fit category + a confidence note.
3. Low-confidence picks are flagged in the DB (`category_confidence = 'low'`) so they surface in the dashboard for a quick manual glance/override rather than getting buried.
4. You can bulk-relabel at any time by editing the `posts.category` column — no re-scrape needed.
