"""Background worker for indexing jobs."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.database import async_session
from app.models.db_models import IndexingJob, File, Folder, Session, Chunk
from app.services.drive import DriveService
from app.services.extraction import ExtractionService, ExtractedDocument
from app.services.embedding import embed_text, embed_batch

PREVIEW_LENGTH = 500


async def claim_next_job() -> IndexingJob | None:
    """Atomically claim the next pending job."""
    async with async_session() as db:
        # Use SELECT FOR UPDATE SKIP LOCKED to prevent race conditions
        result = await db.execute(text("""
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
            RETURNING id
        """))
        await db.commit()
        row = result.first()

        if row is None:
            return None

        # Load the full job with relationships
        job = await db.get(IndexingJob, row[0])
        return job


async def get_access_token_for_folder(folder_id) -> str | None:
    """Get a valid access token for the folder's owner."""
    async with async_session() as db:
        # Get folder to find user_id
        folder = await db.get(Folder, folder_id)
        if not folder:
            return None

        # Get most recent valid session for the user
        result = await db.execute(
            select(Session)
            .where(Session.user_id == folder.user_id)
            .where(Session.expires_at > datetime.now(timezone.utc))
            .order_by(Session.created_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()

        if session:
            return session.access_token
        return None


async def process_job(job: IndexingJob):
    """Process a single indexing job.

    1. Download/export file content from Google Drive
    2. Extract text using ExtractionService (produces structured blocks)
    3. Generate file preview and embedding
    4. Generate embeddings for each block
    5. Store blocks as chunks in database
    6. Update job status to completed
    """
    async with async_session() as db:
        # Load file info
        file = await db.get(File, job.file_id)
        if not file:
            raise ValueError(f"File {job.file_id} not found")

        # Get access token for Drive API
        access_token = await get_access_token_for_folder(job.folder_id)
        if not access_token:
            raise ValueError("No valid access token for folder owner")

        # Initialize services
        drive = DriveService(access_token)
        extraction = ExtractionService()

        # Check if file type is supported
        if not extraction.is_supported(file.mime_type):
            print(f"  Skipping unsupported file type: {file.mime_type}")
            file.index_status = "completed"
            file.file_preview = f"[Unsupported file type: {file.mime_type}]"
            await _mark_job_completed(db, job)
            await _update_folder_progress(db, job.folder_id)
            await db.commit()
            return

        # Extract text based on file type
        print(f"  Extracting text from {file.file_name} ({file.mime_type})")
        extracted: ExtractedDocument

        if extraction.is_google_doc(file.mime_type):
            html_content = await drive.export_google_doc(file.google_file_id, mime_type="text/html")
            extracted = await extraction.extract_google_doc(html_content)
        elif extraction.is_pdf(file.mime_type):
            pdf_content = await drive.download_file(file.google_file_id)
            extracted = await extraction.extract_pdf(pdf_content)
        else:
            # Should not reach here due to is_supported check
            raise ValueError(f"Unexpected mime type: {file.mime_type}")

        if not extracted.blocks:
            print(f"  No content extracted from {file.file_name}")
            file.index_status = "completed"
            file.file_preview = "[No text content extracted]"
            await _mark_job_completed(db, job)
            await _update_folder_progress(db, job.folder_id)
            await db.commit()
            return

        # Create preview from first blocks
        preview_text = _create_preview(extracted)

        # Generate file-level embedding from preview text
        print(f"  Generating file embedding...")
        file_embedding = await embed_text(preview_text)

        # Update file with preview and embedding
        file.file_preview = preview_text
        file.file_embedding = file_embedding
        file.index_status = "indexing"

        # Generate embeddings for all blocks in batches
        print(f"  Processing {len(extracted.blocks)} blocks...")
        block_texts = [block.text for block in extracted.blocks]

        # Process in batches of 32 to avoid API limits
        all_embeddings = []
        batch_size = 32
        for i in range(0, len(block_texts), batch_size):
            batch = block_texts[i:i + batch_size]
            embeddings = await embed_batch(batch)
            all_embeddings.extend(embeddings)
            print(f"    Embedded batch {i // batch_size + 1}/{(len(block_texts) + batch_size - 1) // batch_size}")

        # Store blocks as chunks in database
        print(f"  Storing {len(extracted.blocks)} chunks...")
        for idx, (block, embedding) in enumerate(zip(extracted.blocks, all_embeddings)):
            chunk = Chunk(
                file_id=file.id,
                chunk_text=block.text,
                chunk_embedding=embedding,
                location=block.location,
                chunk_index=idx,
            )
            db.add(chunk)

        # Mark file as completed
        file.index_status = "completed"

        # Mark job as completed
        await _mark_job_completed(db, job)

        # Update folder progress
        await _update_folder_progress(db, job.folder_id)

        await db.commit()
        print(f"  File indexed successfully: {len(extracted.blocks)} chunks")


def _create_preview(extracted: ExtractedDocument) -> str:
    """Create a preview string from the first blocks of extracted content."""
    preview_parts = []
    char_count = 0

    for block in extracted.blocks:
        if char_count >= PREVIEW_LENGTH:
            break
        text = block.text[:PREVIEW_LENGTH - char_count]
        preview_parts.append(text)
        char_count += len(text)

    preview = "\n".join(preview_parts)
    if len(preview) > PREVIEW_LENGTH:
        preview = preview[:PREVIEW_LENGTH]

    return preview


async def _mark_job_completed(db, job: IndexingJob):
    """Mark a job as completed."""
    await db.execute(
        text("""
            UPDATE indexing_jobs
            SET status = 'completed', completed_at = NOW()
            WHERE id = :job_id
        """),
        {"job_id": str(job.id)}
    )


async def _update_folder_progress(db, folder_id):
    """Update folder's files_indexed count and status."""
    await db.execute(
        text("""
            UPDATE folders
            SET files_indexed = (
                SELECT COUNT(*) FROM files
                WHERE folder_id = :folder_id AND index_status = 'completed'
            ),
            index_status = CASE
                WHEN (SELECT COUNT(*) FROM files WHERE folder_id = :folder_id AND index_status = 'completed')
                     = files_total THEN 'ready'
                ELSE 'indexing'
            END
            WHERE id = :folder_id
        """),
        {"folder_id": str(folder_id)}
    )


async def handle_job_failure(job: IndexingJob, error: Exception):
    """Handle a failed job - retry or mark as failed."""
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
                {"job_id": str(job.id), "error": str(error)[:1000]}
            )
        else:
            await db.execute(
                text("""
                    UPDATE indexing_jobs
                    SET status = 'pending', last_error = :error
                    WHERE id = :job_id
                """),
                {"job_id": str(job.id), "error": str(error)[:1000]}
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


async def worker_loop():
    """Main worker loop - polls for jobs and processes them."""
    print("Worker started, polling for jobs...")
    while True:
        try:
            job = await claim_next_job()

            if job is None:
                # No jobs available, wait before polling again
                await asyncio.sleep(2)
                continue

            print(f"Processing job {job.id} for file {job.file_id}...")
            try:
                await process_job(job)
                print(f"Job {job.id} completed successfully")
            except Exception as e:
                print(f"Job {job.id} failed: {e}")
                await handle_job_failure(job, e)

        except Exception as e:
            print(f"Worker error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(worker_loop())
