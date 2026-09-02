import logging
import time
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, Contact, TitleTier
from app.services.hunter_domain_search import HunterDomainSearchError, domain_search

logger = logging.getLogger(__name__)

# Title hierarchy from the sourcing brief -- tier 1 is the primary target.
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

_QUERY_DELAY_SECONDS = 0.3


def _domain_from_website(website: str) -> str:
    if not website:
        return ""
    parsed = urlparse(website if "//" in website else f"//{website}")
    netloc = parsed.netloc or parsed.path
    return netloc.replace("www.", "").split("/")[0]


def _matching_tier_title(position: str, wanted_titles: List[str]) -> Optional[str]:
    """Word-overlap match -- Hunter's `position` field is free text
    ("Plant Operations Manager", "Buyer II"), so neither an exact match nor
    a plain substring check against the tier list catches most real titles
    (e.g. "Plant Manager" is not a substring of "Plant Operations Manager"
    even though it's clearly the same role). Matches when every word of a
    target title appears somewhere in the position."""
    position_lower = (position or "").lower()
    if not position_lower:
        return None
    for title in wanted_titles:
        words = title.lower().split()
        if all(word in position_lower for word in words):
            return title
    return None


def run_contact_finder(
    db: Session,
    companies: List[Company],
    titles: Optional[List[str]] = None,
    max_results_per_query: int = 10,
) -> Tuple[List[Contact], int, List[str]]:
    """For each company, looks up its domain in Hunter and keeps people
    whose title matches the target list.

    One Hunter query per COMPANY (not per company x title like the old
    LinkedIn-search approach) -- a real cost reduction on top of getting
    real data instead of guesses. Returns (contacts_found,
    queries_attempted, warnings).
    """
    titles = titles or TIER_1_TITLES
    found: List[Contact] = []
    queries_attempted = 0
    warnings: List[str] = []
    total_people_seen = 0
    sample_titles_seen: List[str] = []

    for company in companies:
        domain = _domain_from_website(company.website)
        if not domain:
            continue

        queries_attempted += 1
        try:
            people = domain_search(domain, limit=max_results_per_query)
        except HunterDomainSearchError as e:
            logger.warning("Hunter Domain Search failed for '%s': %s", domain, e)
            msg = f"Hunter Domain Search: {e}"
            if msg not in warnings:
                warnings.append(msg)
            continue

        total_people_seen += len(people)

        for person in people:
            if person["title"] and len(sample_titles_seen) < 8:
                sample_titles_seen.append(person["title"])

            matched_title = _matching_tier_title(person["title"], titles)
            if not matched_title or not person["email"]:
                continue

            contact = Contact(
                company_id=company.id,
                first_name=person["first_name"],
                last_name=person["last_name"],
                title=person["title"] or matched_title,
                title_tier=TITLE_TIER_MAP.get(matched_title, TitleTier.tier_2),
                linkedin_url=person["linkedin_url"],
                direct_phone=person["phone"] or company.main_phone,
                email=person["email"],
                # Hunter's own verification status -- "valid", "accept_all",
                # or "unknown" -- not a guess we're labeling ourselves.
                email_confidence=person["email_status"],
                source="hunter_domain_search",
                notes=f"Department: {person['department']}" if person["department"] else None,
            )
            db.add(contact)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                logger.info(
                    "Duplicate contact skipped: %s %s at %s",
                    person["first_name"], person["last_name"], company.name,
                )
                continue

            found.append(contact)

        time.sleep(_QUERY_DELAY_SECONDS)

    if companies and not found and not warnings:
        if total_people_seen == 0:
            warnings.append(
                "Hunter returned 0 people for these company domains -- likely too small/low "
                "web-presence for Hunter's data, not a titles problem. Try larger, more "
                "established companies."
            )
        else:
            sample = ", ".join(f'"{t}"' for t in sample_titles_seen) or "none had a title listed"
            warnings.append(
                f"Hunter found {total_people_seen} people at these domains, but none matched "
                f"your target titles. Actual titles seen: {sample}."
            )

    db.commit()
    return found, queries_attempted, warnings
