import logging
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models import Contact, LeadStatus
from app.services.odoo_client import OdooClient, OdooClientError

logger = logging.getLogger(__name__)


def run_odoo_sync(db: Session, contacts: List[Contact]) -> Dict:
    """Push every APPROVED contact to Odoo as a crm.lead, then mark it SYNCED.

    Only contacts already in `approved` status are sent — this is the human
    approval gate, since enrichment emails are unverified pattern guesses.
    A failure on one contact doesn't stop the rest; failures are collected
    and returned so the caller can retry or investigate.
    """
    client = OdooClient()  # raises OdooClientError immediately if unconfigured
    synced, failed = [], []

    for contact in contacts:
        if contact.status != LeadStatus.approved:
            continue

        company_name = contact.company.name if contact.company else ""
        try:
            client.create_lead(
                name=f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
                company=company_name,
                title=contact.title or "",
                phone=contact.direct_phone or "",
                email=contact.email or "",
                source_note=f"Source: {contact.source}; LinkedIn: {contact.linkedin_url}",
            )
            contact.status = LeadStatus.synced
            db.add(contact)
            synced.append(contact.id)
        except OdooClientError as e:
            logger.error("Odoo sync failed for contact %s: %s", contact.id, e)
            failed.append({"contact_id": contact.id, "error": str(e)})

    db.commit()
    return {"synced": synced, "failed": failed}
