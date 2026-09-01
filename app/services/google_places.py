import logging
from typing import Dict, List

import requests

from app.config import settings

logger = logging.getLogger(__name__)

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Only request the fields we actually use — Places API bills per field
# group, so a narrow field mask keeps cost down.
FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.internationalPhoneNumber,places.websiteUri"


class PlacesSearchError(Exception):
    """Raised when a Places API request can't be completed."""


def places_text_search(query: str, max_results: int = 10) -> List[Dict]:
    """Search for businesses matching a free-text query, e.g.
    'manufacturing company in Anaheim CA'.

    Requires GOOGLE_PLACES_API_KEY in .env — enable "Places API (New)" at
    https://console.cloud.google.com/apis/library/places-backend.googleapis.com
    then create/reuse an API key under Credentials.
    """
    if not settings.google_places_api_key:
        raise PlacesSearchError(
            "Google Places API key not configured — set GOOGLE_PLACES_API_KEY in .env"
        )

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    payload = {"textQuery": query, "maxResultCount": min(max(max_results, 1), 20)}

    try:
        resp = requests.post(PLACES_SEARCH_URL, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("Places API request timed out for query: %s", query)
        raise PlacesSearchError(f"Timed out searching: {query}")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        logger.error("Places API HTTP %s for query '%s': %s", status, query, e)
        raise PlacesSearchError(f"Places API error ({status}) for query: {query}")
    except requests.exceptions.RequestException as e:
        logger.error("Places API request failed for query '%s': %s", query, e)
        raise PlacesSearchError(f"Request failed: {e}")

    return resp.json().get("places", [])
