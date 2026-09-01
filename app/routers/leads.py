from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.odoo_sync import run_odoo_sync
from app.db import get_db
from app.models import Contact, LeadStatus
from app.schemas import ContactOut
from app.services.odoo_client import OdooClientError

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("/", response_model=List[ContactOut])
def list_leads(status: Optional[LeadStatus] = None, db: Session = Depends(get_db)):
    query = db.query(Contact)
    if status:
        query = query.filter(Contact.status == status)
    return query.order_by(Contact.created_at.desc()).all()


@router.post("/{contact_id}/approve", response_model=ContactOut)
def approve_lead(contact_id: int, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Lead not found")
    contact.status = LeadStatus.approved
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.post("/{contact_id}/reject", response_model=ContactOut)
def reject_lead(contact_id: int, db: Session = Depends(get_db)):
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Lead not found")
    contact.status = LeadStatus.rejected
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.post("/sync-approved")
def sync_approved_leads(db: Session = Depends(get_db)):
    """Pushes every approved-but-not-yet-synced lead into Odoo."""
    approved = db.query(Contact).filter(Contact.status == LeadStatus.approved).all()
    if not approved:
        return {"synced": [], "failed": [], "message": "No approved leads to sync"}

    try:
        return run_odoo_sync(db, approved)
    except OdooClientError as e:
        raise HTTPException(status_code=400, detail=str(e))
