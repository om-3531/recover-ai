"""
Job Worker process logic.

Pulls execution jobs from the queue and executes them via JobService.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.jobs.queue import JobQueue, get_default_job_queue
from app.jobs.service import JobService
from app.models.job import RecoveryExecutionJob
from app.providers.registry import ProviderRegistry


class JobWorker:
    """Worker engine for processing queued recovery execution jobs."""

    @classmethod
    def process_next_job(
        cls,
        db: Session,
        queue: Optional[JobQueue] = None,
        registry: Optional[ProviderRegistry] = None,
        actor: str = "job_worker",
    ) -> Optional[RecoveryExecutionJob]:
        """Dequeue and process the next pending job."""
        job_queue = queue or get_default_job_queue()
        job_id = job_queue.dequeue()
        if job_id is None:
            return None

        return JobService.process_job(
            db=db,
            job_id=job_id,
            registry=registry,
            actor=actor,
        )

    @classmethod
    def drain_queue(
        cls,
        db: Session,
        queue: Optional[JobQueue] = None,
        registry: Optional[ProviderRegistry] = None,
        actor: str = "job_worker",
    ) -> int:
        """Process all currently queued jobs."""
        job_queue = queue or get_default_job_queue()
        processed = 0
        while job_queue.size() > 0:
            result = cls.process_next_job(
                db=db,
                queue=job_queue,
                registry=registry,
                actor=actor,
            )
            if result is not None:
                processed += 1
        return processed
