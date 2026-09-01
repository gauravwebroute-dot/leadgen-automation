import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.models import SearchRun
from app.orchestrator import run_pipeline_for_run
from app.schemas import SearchRunCreate, SearchRunOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search-runs", tags=["search"])


def _run_pipeline_background(search_run_id: int, industries: list[str], titles: list[str] | None):
    # Background tasks need their own DB session — the request-scoped one
    # from get_db() closes as soon as the endpoint returns.
    db = SessionLocal()
    try:
        run_pipeline_for_run(db, search_run_id, industries, titles)
    except Exception:
        logger.exception("Pipeline run %d failed", search_run_id)
    finally:
        db.close()


@router.post("/", response_model=SearchRunOut)
def create_search_run(
    payload: SearchRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Kicks off a search run and returns immediately; the pipeline runs in
    the background. Poll GET /search-runs/{id} for result_count, or check
    GET /leads?status=pending once it's done."""
    search_run = SearchRun(
        city=payload.city,
        industry=", ".join(payload.industries),
        titles_targeted=", ".join(payload.titles or []),
    )
    db.add(search_run)
    db.commit()
    db.refresh(search_run)

    background_tasks.add_task(
        _run_pipeline_background, search_run.id, payload.industries, payload.titles
    )
    return search_run


@router.get("/{run_id}", response_model=SearchRunOut)
def get_search_run(run_id: int, db: Session = Depends(get_db)):
    search_run = db.get(SearchRun, run_id)
    if not search_run:
        raise HTTPException(status_code=404, detail="Search run not found")
    return search_run
