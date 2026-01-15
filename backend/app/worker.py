"""Background worker for indexing jobs."""

import asyncio

from app.database import async_session


async def claim_next_job():
    """Atomically claim the next pending job."""
    async with async_session() as db:
        # Use SELECT FOR UPDATE SKIP LOCKED to prevent race conditions
        result = await db.execute("""
            UPDATE indexing_jobs
            SET status = 'processing',
                started_at = NOW(),
                attempts = attempts + 1
            WHERE id = (
                SELECT id FROM indexing_jobs
                WHERE status = 'pending'
                  AND attempts < max_attempts
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
        """)
        await db.commit()
        return result.first()


async def process_job(job):
    """Process a single indexing job."""
    # TODO: Implement actual indexing logic
    # 1. Download/export file content
    # 2. Extract text (type-specific)
    # 3. Generate file preview and embedding
    # 4. Chunk the content
    # 5. Generate chunk embeddings
    # 6. Store everything in database
    pass


async def handle_job_failure(job, error):
    """Handle a failed job - retry or mark as failed."""
    async with async_session() as db:
        if job.attempts >= job.max_attempts:
            await db.execute("""
                UPDATE indexing_jobs
                SET status = 'failed', last_error = :error
                WHERE id = :job_id
            """, {"job_id": job.id, "error": str(error)})
        else:
            await db.execute("""
                UPDATE indexing_jobs
                SET status = 'pending', last_error = :error
                WHERE id = :job_id
            """, {"job_id": job.id, "error": str(error)})
        await db.commit()


async def worker_loop():
    """Main worker loop - polls for jobs and processes them."""
    print("Worker started, polling for jobs...")
    while True:
        job = await claim_next_job()

        if job is None:
            # No jobs available, wait before polling again
            await asyncio.sleep(2)
            continue

        print(f"Processing job {job.id}...")
        try:
            await process_job(job)
            print(f"Job {job.id} completed successfully")
        except Exception as e:
            print(f"Job {job.id} failed: {e}")
            await handle_job_failure(job, e)


if __name__ == "__main__":
    asyncio.run(worker_loop())
