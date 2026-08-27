"""
Execution Jobs REST API routes.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.jobs.schemas import JobListResponse, JobResponse
from app.jobs.service import JobService
from app.models.enums import JobStatus

router = APIRouter(tags=["jobs"])


@router.get(
    "/execution-jobs/{job_id}",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get execution job by ID",
)
def get_execution_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> JobResponse:
    """Retrieve details, status, attempt counts, and result of a recovery execution job."""
    job = JobService.get_job(db=db, job_id=job_id)
    return JobResponse.model_validate(job)


@router.get(
    "/recovery-cases/{case_id}/execution-jobs",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List execution jobs for a recovery case",
)
def list_case_execution_jobs(
    case_id: int,
    status_filter: Optional[JobStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """List all background execution jobs associated with a specific recovery case."""
    items, total = JobService.list_jobs(
        db=db,
        case_id=case_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return JobListResponse(
        items=[JobResponse.model_validate(j) for j in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/execution-jobs",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all execution jobs",
)
def list_execution_jobs(
    case_id: Optional[int] = Query(None),
    approval_id: Optional[int] = Query(None),
    status_filter: Optional[JobStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """List execution jobs with optional filtering by case, approval, and status."""
    items, total = JobService.list_jobs(
        db=db,
        case_id=case_id,
        approval_id=approval_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return JobListResponse(
        items=[JobResponse.model_validate(j) for j in items],
        total=total,
        limit=limit,
        offset=offset,
    )
