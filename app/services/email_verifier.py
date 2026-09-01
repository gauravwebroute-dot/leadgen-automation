import logging
from typing import Dict

import requests

from app.config import settings

logger = logging.getLogger(__name__)

HUNTER_VERIFY_URL = "https://api.hunter.io/v2/email-verifier"


class EmailVerifierError(Exception):
    """Raised when the Hunter verifier request can't be completed."""


def verify_email(email: str) -> Dict:
    """Checks whether an email address is real and deliverable (MX + SMTP
    check), not just a plausible-looking string.

    Requires HUNTER_API_KEY in .env — free tier at hunter.io gives 50
    credits/month (~100 verifications, at 0.5 credit each).

    Returns a dict with at least a "status" key: "valid", "invalid",
    "accept_all", "webmail", "disposable", or "unknown".
    """
    if not settings.hunter_api_key:
        raise EmailVerifierError("Hunter API key not configured — set HUNTER_API_KEY in .env")

    params = {"email": email, "api_key": settings.hunter_api_key}

    try:
        resp = requests.get(HUNTER_VERIFY_URL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("Hunter verifier timed out for %s", email)
        raise EmailVerifierError(f"Timed out verifying: {email}")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        if status == 429:
            raise EmailVerifierError("Hunter monthly credit limit reached")
        logger.error("Hunter verifier HTTP %s for %s: %s", status, email, e)
        raise EmailVerifierError(f"Hunter API error ({status}) for: {email}")
    except requests.exceptions.RequestException as e:
        logger.error("Hunter verifier request failed for %s: %s", email, e)
        raise EmailVerifierError(f"Request failed: {e}")

    return resp.json().get("data", {})
