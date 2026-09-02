from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models import TitleTier, LeadStatus, RunStatus


class SearchRunCreate(BaseModel):
    city: str
    industries: List[str]
    titles: Optional[List[str]] = None
    # Safety cap: only the first N companies found get contact-searched.
    # Contact search costs (titles-per-company) Google CSE queries EACH --
    # this is what actually burns the daily quota, not company search.
    max_companies_for_contacts: Optional[int] = 5


class SearchRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    city: str
    industry: str
    titles_targeted: str
    result_count: int
    status: RunStatus
    error_message: Optional[str] = None
    queries_used: int
    created_at: datetime


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    title_tier: Optional[TitleTier] = None
    linkedin_url: Optional[str] = None
    direct_phone: Optional[str] = None
    email: Optional[str] = None
    email_confidence: Optional[str] = None
    status: LeadStatus
    created_at: datetime
