import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.agents.company_finder import run_company_finder
from app.agents.contact_finder import TIER_1_TITLES, run_contact_finder
from app.agents.enrichment import run_enrichment
from app.models import SearchRun

logger = logging.getLogger(__name__)


def run_pipeline_for_run(
    db: Session,
    search_run_id: int,
    industries: List[str],
    titles: Optional[List[str]] = None,
) -> dict:
    """Runs the discovery pipeline for a SearchRun that already exists in the DB.

    Callers create the SearchRun row first (so the API can return an id
    immediately) and pass its id here — usually from a FastAPI background task.
    """
    titles = titles or TIER_1_TITLES

    search_run = db.get(SearchRun, search_run_id)
    if not search_run:
        raise ValueError(f"SearchRun {search_run_id} not found")

    companies = run_company_finder(db, search_run, industries)
    logger.info("Run %d: found %d companies", search_run.id, len(companies))

    contacts = run_contact_finder(db, companies, titles)
    logger.info("Run %d: found %d contacts", search_run.id, len(contacts))

    enriched = run_enrichment(db, contacts)

    search_run.result_count = len(enriched)
    db.add(search_run)
    db.commit()

    return {
        "search_run_id": search_run.id,
        "companies_found": len(companies),
        "contacts_found": len(contacts),
    }
