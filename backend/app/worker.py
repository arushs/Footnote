"""Background worker for indexing jobs."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.database import async_session
from app.models.db_models import IndexingJob


async def claim_next_job() -> IndexingJob | None:
    """Atomically claim the next pending job."""
    async with async_session() as db:
        # Find the next pending job
        stmt = (
            select(IndexingJob)
            .where(IndexingJob.status == "pending")
            .where(IndexingJob.attempts < IndexingJob.max_attempts)
            .order_by(IndexingJob.priority.desc(), IndexingJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        # Claim the job
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        job.attempts += 1
        await db.commit()
        await db.refresh(job)
        return job


async def complete_job(job_id) -> None:
    """Mark a job as completed."""
    async with async_session() as db:
        stmt = (
            update(IndexingJob)
            .where(IndexingJob.id == job_id)
            .values(status="completed", completed_at=datetime.now(timezone.utc))
        )
        await db.execute(stmt)
        await db.commit()


async def fail_job(job_id, error: str, attempts: int, max_attempts: int) -> None:
    """Handle a failed job - retry or mark as failed."""
    async with async_session() as db:
        if attempts >= max_attempts:
            new_status = "failed"
        else:
            new_status = "pending"

        stmt = (
            update(IndexingJob)
            .where(IndexingJob.id == job_id)
            .values(status=new_status, last_error=error)
        )
        await db.execute(stmt)
        await db.commit()


async def process_job(job: IndexingJob) -> None:
    """Process a single indexing job."""
    # TODO: Implement actual indexing logic
    # 1. Download/export file content
    # 2. Extract text (type-specific)
    # 3. Generate file preview and embedding
    # 4. Chunk the content
    # 5. Generate chunk embeddings
    # 6. Store everything in database
    pass


async def worker_loop():
    """Main worker loop - polls for jobs and processes them."""
    print("Worker started, polling for jobs...")
    while True:
        job = await claim_next_job()

        if job is None:
            await asyncio.sleep(2)
            continue

        print(f"Processing job {job.id}...")
        try:
            await process_job(job)
            await complete_job(job.id)
            print(f"Job {job.id} completed successfully")
        except Exception as e:
            print(f"Job {job.id} failed: {e}")
            await fail_job(job.id, str(e), job.attempts, job.max_attempts)


if __name__ == "__main__":
    asyncio.run(worker_loop())
