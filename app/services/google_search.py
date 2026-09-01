import logging
from typing import Dict, List

import requests

from app.config import settings

logger = logging.getLogger(__name__)

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


class GoogleSearchError(Exception):
    """Raised when a Google Custom Search request can't be completed."""


def google_search(query: str, num: int = 10) -> List[Dict]:
    """Run one Google Custom Search query and return the raw result items.

    Requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX in .env — set these up at
    https://programmablesearchengine.google.com/ (create a search engine,
    turn on "Search the entire web") and
    https://console.cloud.google.com/apis/credentials (enable Custom Search
    API, create an API key).
    """
    if not settings.google_cse_api_key or not settings.google_cse_cx:
        raise GoogleSearchError(
            "Google CSE API key/CX not configured — set GOOGLE_CSE_API_KEY and "
            "GOOGLE_CSE_CX in .env"
        )

    params = {
        "key": settings.google_cse_api_key,
        "cx": settings.google_cse_cx,
        "q": query,
        "num": min(max(num, 1), 10),  # API caps at 10 results per call
    }

    try:
        resp = requests.get(GOOGLE_CSE_URL, params=params, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("Google CSE request timed out for query: %s", query)
        raise GoogleSearchError(f"Timed out searching: {query}")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        logger.error("Google CSE HTTP %s for query '%s': %s", status, query, e)
        if status == 429:
            raise GoogleSearchError("Google CSE daily quota exceeded (free tier is 100 queries/day)")
        raise GoogleSearchError(f"Google API error ({status}) for query: {query}")
    except requests.exceptions.RequestException as e:
        logger.error("Google CSE request failed for query '%s': %s", query, e)
        raise GoogleSearchError(f"Request failed: {e}")

    data = resp.json()
    return data.get("items", [])
