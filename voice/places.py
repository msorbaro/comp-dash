"""Phase 1 - location census. For each voice.brands row, enumerates every US
location via Apify's compass/crawler-google-places actor, scoped to the
pilot states, applies the three hazards the user specified (category filter,
dedupe, alias matching), and upserts into voice.locations.

Also hands back each kept location's rating/review_count as reported by this
same actor call - confirmed via a live test call (2026-09-15) that
compass/crawler-google-places already returns totalScore/reviewsCount
directly on every place, so voice/ratings.py (Phase 2) writes
voice.rating_snapshots from this same fetch instead of a second paid call.
"""
from __future__ import annotations

import math
import os
import re

from apify_client import ApifyClient

from db.connection import get_conn
from scraper.apify_client import dataset_id
from voice.us_states import STATE_NAME_BY_CODE

ACTOR_ID = "compass/crawler-google-places"

# Safety ceiling, not a typical binding constraint - even the most
# location-dense brand realistically has well under this many stores in a
# single state; a live test call showed the actor scans the whole state
# regardless of this cap, so raising it doesn't meaningfully add cost.
MAX_PLACES_PER_SEARCH = 300

# Curated, not exhaustive - checked against the place's PRIMARY category
# (categoryName), case-insensitively, as a substring match. This is what
# catches the Walmart/Costco/Sam's-Club "reviews land on the parent store"
# hazard: a category like "Department store" or "Warehouse club" won't match
# any of these keywords and gets dropped.
AUTOMOTIVE_CATEGORY_KEYWORDS = [
    "auto", "car", "tire", "brake", "mechanic", "oil change", "battery",
    "muffler", "transmission", "vehicle",
]


def _is_automotive_category(category_name: str) -> bool:
    if not category_name:
        return False
    low = category_name.lower()
    return any(kw in low for kw in AUTOMOTIVE_CATEGORY_KEYWORDS)


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (name or "").lower()).strip()


def _match_alias(title: str, aliases: list) -> str | None:
    """Conservative on purpose: only a normalized-title-STARTS-WITH-alias
    counts as a confident match. A location-name-first franchise pattern
    (e.g. "Grandview Tuffy", a real pattern seen in this project's Google
    Ads data) or an unrelated business that merely mentions the brand (e.g.
    "The Grind Brakes Plus Auto Repair" - a real result from a live test
    call, not hypothetical) both get left unmatched rather than guessed, per
    the user's explicit "print unmatched names for me to review rather than
    guessing" instruction. Costs some manual review on genuine
    location-prefixed franchise names; that's the accepted tradeoff."""
    norm_title = _normalize(title)
    for alias in aliases:
        norm_alias = _normalize(alias)
        if norm_alias and norm_title.startswith(norm_alias):
            return alias
    return None


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _dedupe(places: list) -> list:
    """First on placeId (the caller upserts on that as the DB UNIQUE
    constraint, so exact placeId dupes across pages/searches just overwrite
    harmlessly) - this covers the SECOND hazard: the same physical store
    surfacing under two different placeIds, via (normalized name, <=100m)."""
    by_place_id = {p["placeId"]: p for p in places}  # last write wins, fields don't differ
    deduped = []
    for p in by_place_id.values():
        is_dupe = False
        for kept in deduped:
            if _normalize(p["title"]) != _normalize(kept["title"]):
                continue
            loc, kept_loc = p.get("location"), kept.get("location")
            if not loc or not kept_loc:
                continue
            if _haversine_m(loc["lat"], loc["lng"], kept_loc["lat"], kept_loc["lng"]) <= 100:
                is_dupe = True
                break
        if not is_dupe:
            deduped.append(p)
    return deduped


def _fetch_places(client: ApifyClient, search_terms: list, state_name: str) -> list:
    run = client.actor(ACTOR_ID).call(run_input={
        "searchStringsArray": search_terms,
        "countryCode": "us",
        "state": state_name,
        "maxCrawledPlacesPerSearch": MAX_PLACES_PER_SEARCH,
        "language": "en",
        "skipClosedPlaces": True,
    })
    return list(client.dataset(dataset_id(run)).iterate_items())


def run(pilot_state_codes: list) -> dict:
    """Returns a report dict: per-(brand,state) location counts, per-brand
    category-drop counts, the full unmatched-name list (exactly what the
    user asked to review before approving further phases), and
    `rating_rows` - (location_id, avg_rating, review_count) for every kept
    location, handed to voice/ratings.py so Phase 2 needs no extra fetch."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT brand_id, name, aliases FROM voice.brands ORDER BY name")
        brands = cur.fetchall()
    conn.commit()

    client = ApifyClient(os.environ["APIFY_TOKEN"])

    counts = {}
    category_drops = {name: 0 for _bid, name, _al in brands}
    unmatched = []
    non_us_dropped = 0
    rating_rows = []

    for brand_id, brand_name, aliases in brands:
        for state_code in pilot_state_codes:
            state_name = STATE_NAME_BY_CODE[state_code]
            raw_places = _fetch_places(client, list(aliases), state_name)

            kept = []
            for p in raw_places:
                if (p.get("countryCode") or "").upper() != "US":
                    non_us_dropped += 1
                    continue
                if not _is_automotive_category(p.get("categoryName")):
                    category_drops[brand_name] += 1
                    continue
                kept.append(p)

            kept = _dedupe(kept)

            n = 0
            with conn:
                with conn.cursor() as cur:
                    for p in kept:
                        matched_alias = _match_alias(p["title"], aliases)
                        if not matched_alias:
                            unmatched.append((brand_name, state_code, p["title"], p.get("categoryName")))
                            continue
                        loc = p.get("location") or {}
                        cur.execute(
                            """INSERT INTO voice.locations
                                   (brand_id, source, source_place_id, name, street, city, state, zip,
                                    country_code, lat, lng, category, is_active, last_seen_at)
                               VALUES (%(brand_id)s, 'google_maps', %(place_id)s, %(name)s, %(street)s,
                                       %(city)s, %(state)s, %(zip)s, %(country_code)s, %(lat)s, %(lng)s,
                                       %(category)s, TRUE, now())
                               ON CONFLICT (source, source_place_id) DO UPDATE
                                   SET name = EXCLUDED.name, street = EXCLUDED.street, city = EXCLUDED.city,
                                       state = EXCLUDED.state, zip = EXCLUDED.zip, lat = EXCLUDED.lat,
                                       lng = EXCLUDED.lng, category = EXCLUDED.category,
                                       is_active = TRUE, last_seen_at = now()
                               RETURNING location_id""",
                            {
                                "brand_id": brand_id, "place_id": p["placeId"], "name": p.get("title"),
                                "street": p.get("street"), "city": p.get("city"), "state": state_code,
                                "zip": p.get("postalCode"), "country_code": p.get("countryCode"),
                                "lat": loc.get("lat"), "lng": loc.get("lng"), "category": p.get("categoryName"),
                            },
                        )
                        location_id = cur.fetchone()[0]
                        n += 1
                        rating_rows.append((location_id, p.get("totalScore"), p.get("reviewsCount")))
            counts[(brand_name, state_code)] = n

    return {
        "counts": counts, "category_drops": category_drops, "unmatched": unmatched,
        "non_us_dropped": non_us_dropped, "rating_rows": rating_rows,
    }
