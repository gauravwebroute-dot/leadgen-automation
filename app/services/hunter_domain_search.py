import logging
from typing import Dict, List

import requests

from app.config import settings

logger = logging.getLogger(__name__)

HUNTER_DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"


class HunterDomainSearchError(Exception):
    """Raised when a Hunter Domain Search request can't be completed."""


def domain_search(domain: str, limit: int = 10) -> List[Dict]:
    """Returns real people found at a domain -- name, title, department,
    a verified (or scored) email, and phone/LinkedIn when available.

    Unlike the old LinkedIn-search + email-pattern-guess approach, nothing
    here is inferred: every field comes directly from Hunter's own data,
    with its own verification status attached per email.

    Requires HUNTER_API_KEY in .env (same key already used for email
    verification elsewhere in this project).
    """
    if not settings.hunter_api_key:
        raise HunterDomainSearchError("Hunter API key not configured — set HUNTER_API_KEY in .env")

    if not domain:
        return []

    params = {
        "domain": domain,
        "api_key": settings.hunter_api_key,
        "limit": min(max(limit, 1), 100),
    }

    try:
        resp = requests.get(HUNTER_DOMAIN_SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("Hunter Domain Search timed out for domain: %s", domain)
        raise HunterDomainSearchError(f"Timed out searching domain: {domain}")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        if status == 429:
            raise HunterDomainSearchError("Hunter monthly credit limit reached")
        logger.error("Hunter Domain Search HTTP %s for %s: %s", status, domain, e)
        raise HunterDomainSearchError(f"Hunter API error ({status}) for domain: {domain}")
    except requests.exceptions.RequestException as e:
        logger.error("Hunter Domain Search request failed for %s: %s", domain, e)
        raise HunterDomainSearchError(f"Request failed: {e}")

    data = resp.json().get("data", {}) or {}
    emails = data.get("emails", []) or []

    normalized = []
    for entry in emails:
        verification = entry.get("verification") or {}
        normalized.append(
            {
                "first_name": entry.get("first_name") or "",
                "last_name": entry.get("last_name") or "",
                "title": entry.get("position") or "",
                "department": entry.get("department") or "",
                "email": entry.get("value") or "",
                "email_status": verification.get("status") or "unknown",
                "phone": entry.get("phone_number") or "",
                "linkedin_url": entry.get("linkedin") or entry.get("linkedin_url") or "",
            }
        )
    return normalized
