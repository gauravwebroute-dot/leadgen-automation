import logging
from typing import Dict, List

from app.config import settings

logger = logging.getLogger(__name__)


class OutscraperError(Exception):
    """Raised when an Outscraper request can't be completed."""


def maps_search(query: str, limit: int = 10) -> List[Dict]:
    """Searches Google Maps via Outscraper and returns normalized business
    records: {name, website, phone}.

    Requires OUTSCRAPER_API_KEY in .env — sign up at outscraper.com, the
    free tier includes monthly credits good for testing before you commit
    to a paid people-data API.

    Uses the official `outscraper` PyPI package rather than hand-rolling
    the REST call, since Outscraper's own client handles their
    request/poll pattern for you.
    """
    if not settings.outscraper_api_key:
        raise OutscraperError("Outscraper API key not configured — set OUTSCRAPER_API_KEY in .env")

    try:
        from outscraper import ApiClient
    except ImportError:
        raise OutscraperError("outscraper package not installed — run: pip install outscraper")

    client = ApiClient(api_key=settings.outscraper_api_key)

    try:
        # google_maps_search returns a list of result-sets (one per query);
        # we pass a single query so we want the first (and only) result-set.
        results = client.google_maps_search([query], limit=limit, language="en", region="us")
    except Exception as e:
        logger.error("Outscraper request failed for '%s': %s", query, e)
        raise OutscraperError(f"Outscraper request failed: {e}")

    places = results[0] if results else []

    normalized = []
    for place in places:
        normalized.append(
            {
                "name": place.get("name", ""),
                "website": place.get("site", ""),
                "phone": place.get("phone", ""),
            }
        )
    return normalized
