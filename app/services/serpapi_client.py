import logging
from typing import Dict, List

import requests

from app.config import settings

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"


class SerpApiError(Exception):
    """Raised when a SerpApi request can't be completed."""


def maps_search(query: str, limit: int = 10) -> List[Dict]:
    """Searches Google Maps via SerpApi and returns normalized business
    records: {name, website, phone}.

    Requires SERPAPI_API_KEY in .env -- serpapi.com's free tier includes
    100 searches/month.
    """
    if not settings.serpapi_api_key:
        raise SerpApiError("SerpApi key not configured — set SERPAPI_API_KEY in .env")

    params = {
        "api_key": settings.serpapi_api_key,
        "engine": "google_maps",
        "q": query,
        "type": "search",
    }

    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("SerpApi request timed out for query: %s", query)
        raise SerpApiError(f"Timed out searching: {query}")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        logger.error("SerpApi HTTP %s for query '%s': %s", status, query, e)
        raise SerpApiError(f"SerpApi error ({status}) for query: {query}")
    except requests.exceptions.RequestException as e:
        logger.error("SerpApi request failed for query '%s': %s", query, e)
        raise SerpApiError(f"Request failed: {e}")

    data = resp.json()
    if data.get("search_metadata", {}).get("status") == "Error":
        raise SerpApiError(data.get("error", "Unknown SerpApi error"))

    places = data.get("local_results", [])
    if isinstance(places, dict):
        # SerpApi returns a single dict (not a list) when Google resolves
        # the query to one specific place instead of a results list.
        places = [places]

    normalized = []
    for place in places[:limit]:
        normalized.append(
            {
                "name": place.get("title", ""),
                "website": place.get("website", ""),
                "phone": place.get("phone", ""),
            }
        )
    return normalized
