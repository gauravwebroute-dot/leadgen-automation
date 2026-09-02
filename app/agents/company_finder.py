import logging
import time
from typing import Dict, List, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, SearchRun
from app.services.google_places import PlacesSearchError, places_text_search
from app.services.outscraper_client import OutscraperError, maps_search

logger = logging.getLogger(__name__)

QUERY_TEMPLATES = [
    "{industry} company in {city} CA",
    "{industry} manufacturer in {city} CA",
]

_QUERY_DELAY_SECONDS = 0.15


def _search_places(query: str, limit: int) -> Tuple[List[Dict], str | None]:
    """Runs one company search through whichever provider is configured,
    always returning the same shape: [{name, website, phone}, ...].

    Returns (results, warning) -- warning is None on success, or a
    human-readable reason on failure, so the caller can surface it in the
    dashboard instead of only in server logs.

    Swapping providers later (e.g. to a paid people-data API) only means
    adding a branch here -- callers never change.
    """
    provider = settings.company_discovery_provider

    if provider == "outscraper":
        try:
            return maps_search(query, limit=limit), None
        except OutscraperError as e:
            logger.warning("Outscraper search failed for '%s': %s", query, e)
            return [], f"Outscraper: {e}"

    if provider == "places":
        try:
            places = places_text_search(query, max_results=limit)
        except PlacesSearchError as e:
            logger.warning("Places search failed for '%s': %s", query, e)
            return [], f"Places API: {e}"
        return [
            {
                "name": (p.get("displayName") or {}).get("text", ""),
                "website": p.get("websiteUri", ""),
                "phone": p.get("internationalPhoneNumber", ""),
            }
            for p in places
        ], None

    return [], f"Unknown COMPANY_DISCOVERY_PROVIDER: {provider!r}"


def run_company_finder(
    db: Session,
    search_run: SearchRun,
    industries: List[str],
    max_results_per_query: int = 10,
) -> Tuple[List[Company], int, List[str]]:
    """Search for companies matching each industry near search_run.city.
    Provider (Outscraper for testing, Places for production-grade calls)
    is picked via COMPANY_DISCOVERY_PROVIDER in .env. Deduplicates on
    (name, city).

    Returns (companies_found, queries_attempted, warnings) -- warnings are
    deduplicated failure reasons collected across all queries in this run,
    meant to be shown directly in the dashboard.
    """
    found: List[Company] = []
    queries_attempted = 0
    warnings: List[str] = []

    for industry in industries:
        for template in QUERY_TEMPLATES:
            query = template.format(industry=industry, city=search_run.city)
            queries_attempted += 1
            results, warning = _search_places(query, max_results_per_query)
            if warning and warning not in warnings:
                warnings.append(warning)

            for result in results:
                name = (result.get("name") or "").strip()
                if not name:
                    continue

                company = Company(
                    name=name,
                    industry=industry,
                    city=search_run.city,
                    website=result.get("website", ""),
                    main_phone=result.get("phone", ""),
                    source=f"{settings.company_discovery_provider}",
                    search_run_id=search_run.id,
                )
                db.add(company)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    logger.info("Duplicate company skipped: %s (%s)", name, search_run.city)
                    continue

                found.append(company)

            time.sleep(_QUERY_DELAY_SECONDS)

    if not found and not warnings:
        # Provider worked (no errors) but genuinely returned nothing --
        # worth saying explicitly rather than leaving it ambiguous.
        warnings.append(
            f"{settings.company_discovery_provider} returned 0 results for all queries -- "
            "try a broader industry term or a different/nearby city."
        )

    db.commit()
    return found, queries_attempted, warnings
