"""Background worker for indexing jobs."""

import asyncio
import json
import logging
import uuid

from sqlalchemy import text

from app.database import async_session
from app.models.db_models import File, Chunk, IndexingJob, Session
from app.services.drive import DriveService
from app.services.extraction import ExtractionService
from app.services.chunking import chunk_document, generate_file_preview
from app.services.embedding import embed_text, embed_batch


def format_vector(embedding: list[float]) -> str:
    """Format embedding list as PostgreSQL vector string."""
    return "[" + ",".join(str(x) for x in embedding) + "]"

logger = logging.getLogger(__name__)


async def claim_next_job() -> IndexingJob | None:
    """Atomically claim the next pending job."""
    async with async_session() as db:
        # Use SELECT FOR UPDATE SKIP LOCKED to prevent race conditions
        result = await db.execute(
            text("""
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
                RETURNING id, folder_id, file_id, status, priority, attempts, max_attempts, last_error
            """)
        )
        await db.commit()
        row = result.first()
        if row:
            return IndexingJob(
                id=row.id,
                folder_id=row.folder_id,
                file_id=row.file_id,
                status=row.status,
                priority=row.priority,
                attempts=row.attempts,
                max_attempts=row.max_attempts,
                last_error=row.last_error,
            )
        return None


async def get_user_session_for_folder(folder_id: uuid.UUID) -> Session | None:
    """Get a valid user session for accessing files in a folder."""
    async with async_session() as db:
        result = await db.execute(
            text("""
                SELECT s.id, s.user_id, s.access_token, s.refresh_token, s.expires_at
                FROM sessions s
                JOIN folders f ON f.user_id = s.user_id
                WHERE f.id = :folder_id
                  AND s.expires_at > NOW()
                ORDER BY s.expires_at DESC
                LIMIT 1
            """),
            {"folder_id": str(folder_id)},
        )
        row = result.first()
        if row:
            return Session(
                id=row.id,
                user_id=row.user_id,
                access_token=row.access_token,
                refresh_token=row.refresh_token,
                expires_at=row.expires_at,
            )
        return None


async def get_file_info(file_id: uuid.UUID) -> File | None:
    """Get file information from the database."""
    async with async_session() as db:
        result = await db.execute(
            text("""
                SELECT id, folder_id, google_file_id, file_name, mime_type,
                       modified_time, file_preview, index_status
                FROM files
                WHERE id = :file_id
            """),
            {"file_id": str(file_id)},
        )
        row = result.first()
        if row:
            return File(
                id=row.id,
                folder_id=row.folder_id,
                google_file_id=row.google_file_id,
                file_name=row.file_name,
                mime_type=row.mime_type,
                modified_time=row.modified_time,
                file_preview=row.file_preview,
                index_status=row.index_status,
            )
        return None


async def process_job(job: IndexingJob) -> None:
    """
    Process a single indexing job.

    Steps:
    1. Get user session for Google Drive access
    2. Download/export file content
    3. Extract text (type-specific)
    4. Generate file preview and embedding
    5. Chunk the content
    6. Generate chunk embeddings
    7. Store everything in database
    """
    logger.info(f"Processing job {job.id} for file {job.file_id}")

    # Get session for Drive access
    session = await get_user_session_for_folder(job.folder_id)
    if not session:
        raise ValueError(f"No valid session found for folder {job.folder_id}")

    # Get file info
    file_info = await get_file_info(job.file_id)
    if not file_info:
        raise ValueError(f"File {job.file_id} not found")

    # Initialize services
    drive = DriveService(session.access_token)
    extraction = ExtractionService()

    # Step 1: Download/export file content based on type
    if extraction.is_google_doc(file_info.mime_type):
        logger.info(f"Exporting Google Doc: {file_info.file_name}")
        html_content = await drive.export_google_doc(file_info.google_file_id)
        document = await extraction.extract_google_doc(html_content)
    elif extraction.is_pdf(file_info.mime_type):
        logger.info(f"Downloading PDF: {file_info.file_name}")
        pdf_content = await drive.download_file(file_info.google_file_id)
        document = await extraction.extract_pdf(pdf_content)
    else:
        raise ValueError(f"Unsupported file type: {file_info.mime_type}")

    if not document.blocks:
        logger.warning(f"No content extracted from {file_info.file_name}")
        await mark_job_completed(job)
        await update_file_status(job.file_id, "indexed")
        return

    # Step 2: Generate file preview
    preview = generate_file_preview(document.blocks)
    logger.info(f"Generated preview ({len(preview)} chars)")

    # Step 3: Generate file-level embedding
    file_embedding = await embed_text(preview) if preview else None

    # Step 4: Chunk the document
    chunks = chunk_document(document.blocks)
    logger.info(f"Created {len(chunks)} chunks")

    if not chunks:
        await mark_job_completed(job)
        await update_file_status(job.file_id, "indexed")
        return

    # Step 5: Generate chunk embeddings in batches
    chunk_texts = [c.text for c in chunks]
    chunk_embeddings = await embed_batch(chunk_texts)

    # Step 6: Store everything in database
    async with async_session() as db:
        # Update file with preview and embedding
        await db.execute(
            text("""
                UPDATE files
                SET file_preview = :preview,
                    file_embedding = :embedding::vector,
                    index_status = 'indexed'
                WHERE id = :file_id
            """),
            {
                "preview": preview,
                "embedding": format_vector(file_embedding) if file_embedding else None,
                "file_id": str(job.file_id),
            },
        )

        # Delete any existing chunks for this file (in case of re-indexing)
        await db.execute(
            text("DELETE FROM chunks WHERE file_id = :file_id"),
            {"file_id": str(job.file_id)},
        )

        # Insert chunks
        for chunk, embedding in zip(chunks, chunk_embeddings):
            await db.execute(
                text("""
                    INSERT INTO chunks (id, file_id, chunk_text, chunk_embedding, location, chunk_index)
                    VALUES (:id, :file_id, :chunk_text, :chunk_embedding::vector, :location::jsonb, :chunk_index)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "file_id": str(job.file_id),
                    "chunk_text": chunk.text,
                    "chunk_embedding": format_vector(embedding),
                    "location": json.dumps(chunk.location),
                    "chunk_index": chunk.chunk_index,
                },
            )

        await db.commit()

    # Mark job as completed
    await mark_job_completed(job)

    # Update folder progress
    await update_folder_progress(job.folder_id)

    logger.info(f"Successfully indexed {file_info.file_name} with {len(chunks)} chunks")


async def mark_job_completed(job: IndexingJob) -> None:
    """Mark an indexing job as completed."""
    async with async_session() as db:
        await db.execute(
            text("""
                UPDATE indexing_jobs
                SET status = 'completed', completed_at = NOW()
                WHERE id = :job_id
            """),
            {"job_id": str(job.id)},
        )
        await db.commit()


async def update_file_status(file_id: uuid.UUID, status: str) -> None:
    """Update file index status."""
    async with async_session() as db:
        await db.execute(
            text("UPDATE files SET index_status = :status WHERE id = :file_id"),
            {"status": status, "file_id": str(file_id)},
        )
        await db.commit()


async def update_folder_progress(folder_id: uuid.UUID) -> None:
    """Update folder indexing progress."""
    async with async_session() as db:
        # Count completed files
        result = await db.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE index_status = 'indexed') as indexed
                FROM files
                WHERE folder_id = :folder_id
            """),
            {"folder_id": str(folder_id)},
        )
        row = result.first()
        total = row.total if row else 0
        indexed = row.indexed if row else 0

        # Update folder
        status = "ready" if indexed == total else "indexing"
        await db.execute(
            text("""
                UPDATE folders
                SET files_indexed = :indexed,
                    files_total = :total,
                    index_status = :status,
                    updated_at = NOW()
                WHERE id = :folder_id
            """),
            {
                "indexed": indexed,
                "total": total,
                "status": status,
                "folder_id": str(folder_id),
            },
        )
        await db.commit()


async def handle_job_failure(job: IndexingJob, error: Exception) -> None:
    """Handle a failed job - retry or mark as failed."""
    logger.error(f"Job {job.id} failed: {error}")

    async with async_session() as db:
        # Update file status
        await db.execute(
            text("""
                UPDATE files SET index_status = 'failed'
                WHERE id = :file_id
            """),
            {"file_id": str(job.file_id)}
        )

        if job.attempts >= job.max_attempts:
            await db.execute(
                text("""
                    UPDATE indexing_jobs
                    SET status = 'failed', last_error = :error
                    WHERE id = :job_id
                """),
                {"job_id": str(job.id), "error": str(error)[:1000]},
            )
        else:
            await db.execute(
                text("""
                    UPDATE indexing_jobs
                    SET status = 'pending', last_error = :error
                    WHERE id = :job_id
                """),
                {"job_id": str(job.id), "error": str(error)[:1000]},
            )
            # Reset file status for retry
            await db.execute(
                text("""
                    UPDATE files SET index_status = 'pending'
                    WHERE id = :file_id
                """),
                {"file_id": str(job.file_id)}
            )

        await db.commit()


async def worker_loop() -> None:
    """Main worker loop - polls for jobs and processes them."""
    logger.info("Worker started, polling for jobs...")

    while True:
        try:
            job = await claim_next_job()

            if job is None:
                # No jobs available, wait before polling again
                await asyncio.sleep(2)
                continue

            logger.info(f"Processing job {job.id}...")
            try:
                await process_job(job)
                logger.info(f"Job {job.id} completed successfully")
            except Exception as e:
                await handle_job_failure(job, e)

        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_loop())
