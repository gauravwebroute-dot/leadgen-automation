import datetime
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Enum,
    UniqueConstraint,
    Text,
)
from sqlalchemy.orm import relationship

from app.db import Base


class TitleTier(str, enum.Enum):
    tier_1 = "tier_1"  # Facilities/Maintenance/Plant/Purchasing — best targets
    tier_2 = "tier_2"  # Operations/Engineering/Procurement
    tier_3 = "tier_3"  # Owner/President/GM — fallback for small companies


class LeadStatus(str, enum.Enum):
    pending = "pending"    # found, not yet reviewed
    approved = "approved"  # human approved, ready to sync
    rejected = "rejected"  # human rejected, will not sync
    synced = "synced"      # pushed to Odoo


class RunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class SearchRun(Base):
    __tablename__ = "search_runs"

    id = Column(Integer, primary_key=True)
    city = Column(String, nullable=False)
    industry = Column(String, nullable=False)
    titles_targeted = Column(String, nullable=False)
    result_count = Column(Integer, default=0)
    status = Column(Enum(RunStatus, native_enum=False), default=RunStatus.running, nullable=False)
    error_message = Column(Text, nullable=True)
    # Total external API calls this run made (company + contact provider
    # calls combined) -- shown in the dashboard so a spike in usage is
    # visible instead of a mystery.
    queries_used = Column(Integer, default=0)
    # Deduplicated, human-readable reasons the run found nothing (bad key,
    # 0 results from provider, quota hit) -- shown directly in the
    # dashboard instead of requiring a trip to the server logs.
    warnings = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    companies = relationship("Company", back_populates="search_run")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    industry = Column(String)
    city = Column(String)
    website = Column(String)
    main_phone = Column(String)
    source = Column(String)
    search_run_id = Column(Integer, ForeignKey("search_runs.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    search_run = relationship("SearchRun", back_populates="companies")
    contacts = relationship("Contact", back_populates="company")

    __table_args__ = (UniqueConstraint("name", "city", name="uq_company_name_city"),)


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    title = Column(String)
    title_tier = Column(Enum(TitleTier))
    linkedin_url = Column(String)
    direct_phone = Column(String)
    email = Column(String)
    email_confidence = Column(String)  # "verified" | "pattern_guess" | "unknown"
    source = Column(String)
    notes = Column(Text)
    status = Column(Enum(LeadStatus), default=LeadStatus.pending, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    company = relationship("Company", back_populates="contacts")

    __table_args__ = (
        UniqueConstraint("company_id", "first_name", "last_name", name="uq_contact_company_name"),
    )
