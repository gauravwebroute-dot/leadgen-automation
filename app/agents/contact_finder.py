import logging
import re
import time
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, Contact, TitleTier
from app.services.google_search import GoogleSearchError, google_search

logger = logging.getLogger(__name__)

# Title hierarchy from the sourcing brief — tier 1 is the primary target.
TIER_1_TITLES = [
    "Facilities Manager",
    "Maintenance Manager",
    "Plant Manager",
    "Purchasing Manager",
    "Purchasing Agent",
    "Buyer",
]
TIER_2_TITLES = [
    "Operations Manager",
    "General Manager",
    "Procurement Manager",
    "Engineering Manager",
]
TIER_3_TITLES = ["Owner", "President", "VP Operations"]

TITLE_TIER_MAP = {t: TitleTier.tier_1 for t in TIER_1_TITLES}
TITLE_TIER_MAP.update({t: TitleTier.tier_2 for t in TIER_2_TITLES})
TITLE_TIER_MAP.update({t: TitleTier.tier_3 for t in TIER_3_TITLES})

# Matches a leading "First Last" in a LinkedIn result title, e.g.
# "John Smith - Plant Manager - ABC Manufacturing | LinkedIn"
_NAME_RE = re.compile(r"^([A-Z][a-zA-Z'-]+)\s+([A-Z][a-zA-Z'-]+)")

_QUERY_DELAY_SECONDS = 0.2


def _guess_name(snippet_title: str) -> Tuple[Optional[str], Optional[str]]:
    """Best-effort first/last name extraction. Returns (None, None) if unclear —
    callers should skip the result rather than guess further."""
    match = _NAME_RE.match(snippet_title.strip())
    if not match:
        return None, None
    return match.group(1), match.group(2)


def run_contact_finder(
    db: Session,
    companies: List[Company],
    titles: Optional[List[str]] = None,
    max_results_per_query: int = 5,
) -> Tuple[List[Contact], int]:
    """For each company, search for people holding each target title.

    Uses `site:linkedin.com/in` — this queries Google's public index, not
    linkedin.com directly, matching the manual research process it's
    automating rather than scraping LinkedIn itself.

    This is the expensive stage against your Google CSE daily quota: it's
    one query per (company x title) — 10 companies x 6 default titles is
    60 queries in a single run. Returns (contacts_found, queries_attempted)
    so callers can track usage.
    """
    titles = titles or TIER_1_TITLES
    found: List[Contact] = []
    queries_attempted = 0

    for company in companies:
        for title in titles:
            query = f'site:linkedin.com/in "{title}" "{company.name}"'
            queries_attempted += 1

            try:
                items = google_search(query, num=max_results_per_query)
            except GoogleSearchError as e:
                logger.warning("Contact search failed for '%s': %s", query, e)
                continue

            for item in items:
                first, last = _guess_name(item.get("title", ""))
                if not first:
                    continue

                contact = Contact(
                    company_id=company.id,
                    first_name=first,
                    last_name=last,
                    title=title,
                    title_tier=TITLE_TIER_MAP.get(title, TitleTier.tier_2),
                    linkedin_url=item.get("link", ""),
                    source="google_cse_linkedin",
                    notes=(item.get("snippet", "") or "")[:500],
                )
                db.add(contact)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    logger.info("Duplicate contact skipped: %s %s at %s", first, last, company.name)
                    continue

                found.append(contact)

            time.sleep(_QUERY_DELAY_SECONDS)

    db.commit()
    return found, queries_attempted
