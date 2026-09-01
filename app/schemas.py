from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models import TitleTier, LeadStatus


class SearchRunCreate(BaseModel):
    city: str
    industries: List[str]
    titles: Optional[List[str]] = None


class SearchRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    city: str
    industry: str
    titles_targeted: str
    result_count: int
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
