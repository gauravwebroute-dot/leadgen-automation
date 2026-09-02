import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.agents.company_finder import run_company_finder
from app.agents.contact_finder import TIER_1_TITLES, run_contact_finder
from app.models import RunStatus, SearchRun

logger = logging.getLogger(__name__)

DEFAULT_MAX_COMPANIES_FOR_CONTACTS = 5


def run_pipeline_for_run(
    db: Session,
    search_run_id: int,
    industries: List[str],
    titles: Optional[List[str]] = None,
    max_companies_for_contacts: Optional[int] = None,
) -> dict:
    """Runs the discovery pipeline for a SearchRun that already exists in the DB.

    Callers create the SearchRun row first (so the API can return an id
    immediately) and pass its id here -- usually from a FastAPI background task.

    max_companies_for_contacts caps how many companies get contact-searched
    -- each costs one Hunter Domain Search credit, so this protects your
    monthly Hunter quota the same way it used to protect the Google CSE
    daily quota.
    """
    titles = titles or TIER_1_TITLES
    cap = max_companies_for_contacts or DEFAULT_MAX_COMPANIES_FOR_CONTACTS

    search_run = db.get(SearchRun, search_run_id)
    if not search_run:
        raise ValueError(f"SearchRun {search_run_id} not found")

    companies, company_queries, company_warnings = run_company_finder(db, search_run, industries)
    logger.info("Run %d: found %d companies (%d queries)", search_run.id, len(companies), company_queries)

    companies_for_contacts = companies[:cap]
    if len(companies) > cap:
        logger.info(
            "Run %d: capping contact search to %d of %d companies to protect Hunter quota",
            search_run.id, cap, len(companies),
        )

    # Hunter Domain Search returns real names, titles, and (already
    # verified) emails directly -- no separate enrichment/guessing pass
    # needed anymore.
    contacts, contact_queries, contact_warnings = run_contact_finder(db, companies_for_contacts, titles)
    logger.info("Run %d: found %d contacts (%d queries)", search_run.id, len(contacts), contact_queries)

    all_warnings = company_warnings + contact_warnings

    search_run.result_count = len(contacts)
    search_run.queries_used = company_queries + contact_queries
    search_run.warnings = "\n".join(all_warnings)[:2000] if all_warnings else None
    search_run.status = RunStatus.completed
    db.add(search_run)
    db.commit()

    return {
        "search_run_id": search_run.id,
        "companies_found": len(companies),
        "contacts_found": len(contacts),
        "queries_used": search_run.queries_used,
        "warnings": all_warnings,
    }
