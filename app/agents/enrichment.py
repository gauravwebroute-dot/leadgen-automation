import logging
from typing import List
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import Contact
from app.services.email_verifier import EmailVerifierError, verify_email

logger = logging.getLogger(__name__)


def _domain_from_website(website: str) -> str:
    if not website:
        return ""
    parsed = urlparse(website if "//" in website else f"//{website}")
    netloc = parsed.netloc or parsed.path
    return netloc.replace("www.", "").split("/")[0]


def run_enrichment(db: Session, contacts: List[Contact]) -> List[Contact]:
    """Guesses an email (first.last@domain), then verifies it through
    Hunter's Email Verifier API before trusting it.

    email_confidence ends up as one of:
      - "verified"       -- Hunter confirmed the mailbox is real
      - "risky"          -- Hunter returned accept_all/webmail/unknown; usable
                             but not certain, flag for a human look
      - "invalid"        -- Hunter confirmed it does NOT exist; email cleared
      - "unverified_guess" -- Hunter API not configured, guess only
      - "unknown"         -- no website/name to even guess from

    Nothing is marked "verified" without a confirming API response --
    if HUNTER_API_KEY isn't set, guesses are labeled honestly instead of
    silently passed off as trustworthy.
    """
    for contact in contacts:
        company = contact.company
        domain = _domain_from_website(company.website if company else "")

        if not (domain and contact.first_name and contact.last_name):
            contact.email_confidence = "unknown"
            db.add(contact)
            continue

        guess = f"{contact.first_name.lower()}.{contact.last_name.lower()}@{domain}"

        try:
            result = verify_email(guess)
            status = result.get("status", "unknown")
            if status == "valid":
                contact.email = guess
                contact.email_confidence = "verified"
            elif status == "invalid":
                contact.email = None
                contact.email_confidence = "invalid"
            else:  # accept_all, webmail, disposable, unknown
                contact.email = guess
                contact.email_confidence = "risky"
        except EmailVerifierError as e:
            logger.warning("Email verification unavailable for %s: %s", guess, e)
            contact.email = guess
            contact.email_confidence = "unverified_guess"

        if company and company.main_phone and not contact.direct_phone:
            contact.direct_phone = company.main_phone

        db.add(contact)

    db.commit()
    return contacts
