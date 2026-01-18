"""Celery tasks for file indexing."""

import asyncio
import json
import logging
import uuid

import httpx
from sqlalchemy import text

from app.celery_app import celery_app
from app.config import settings
from app.database import get_task_session
from app.exceptions import (
    PERMANENT_ERRORS,
    TRANSIENT_ERRORS,
    PermanentIndexingError,
    TransientIndexingError,
)
from app.models import File, Session
from app.services.anthropic import get_client as get_anthropic_client
from app.services.drive import DriveService
from app.services.file.chunking import DocumentChunk, chunk_document, generate_file_preview
from app.services.file.embedding import embed_document, embed_documents_batch
from app.services.file.extraction import ExtractionService
from app.services.posthog import LLMTimer, track_llm_generation
from app.utils import format_vector

logger = logging.getLogger(__name__)


CONTEXT_PROMPT = """Document: {file_name}

{document_excerpt}

---
Chunk to contextualize:
{chunk_text}

Write 1-2 sentences situating this chunk within the document. Output only the context."""


async def _generate_single_context(
    client,
    file_name: str,
    document_excerpt: str,
    chunk_text: str,
    max_retries: int = 3,
) -> str | None:
    """Generate context for a single chunk with retry and rate limit handling."""
    import anthropic

    for attempt in range(max_retries):
        try:
            with LLMTimer() as timer:
                response = await client.messages.create(
                    model=settings.claude_fast_model,
                    max_tokens=100,
                    temperature=0.0,
                    messages=[
                        {
                            "role": "user",
                            "content": CONTEXT_PROMPT.format(
                                file_name=file_name,
                                document_excerpt=document_excerpt,
                                chunk_text=chunk_text,
                            ),
                        }
                    ],
                )

            # Track LLM generation in PostHog (background job, no user context)
            track_llm_generation(
                distinct_id="system",
                model=settings.claude_fast_model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=timer.elapsed_ms,
                properties={"mode": "contextual_chunking", "file_name": file_name},
            )

            return response.content[0].text.strip()
        except anthropic.RateLimitError:
            wait_time = (2**attempt) * 2  # 2s, 4s, 8s
            logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1})")
            await asyncio.sleep(wait_time)
            if attempt == max_retries - 1:
                logger.error(f"Rate limit retries exhausted for chunk in {file_name}")
                return None
        except Exception as e:
            logger.warning(f"Context generation failed: {e}")
            return None
    return None


async def _generate_chunk_contexts(
    file_name: str,
    full_document: str,
    chunks: list[DocumentChunk],
    max_concurrent: int = 2,
) -> list[str]:
    """Generate contexts for all chunks in parallel with bounded concurrency."""
    if len(full_document) < 500:
        logger.debug(f"Skipping context generation for short document: {file_name}")
        return [chunk.text for chunk in chunks]

    doc_excerpt = full_document[:6000]
    if len(full_document) > 6000:
        doc_excerpt += "\n[...truncated...]"

    client = get_anthropic_client()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def generate_with_limit(chunk: DocumentChunk) -> str:
        async with semaphore:
            ctx = await _generate_single_context(client, file_name, doc_excerpt, chunk.text)
            if ctx:
                return f"{ctx}\n\n{chunk.text}"
            return chunk.text

    logger.info(f"Generating context for {len(chunks)} chunks in {file_name}")
    results = await asyncio.gather(*[generate_with_limit(c) for c in chunks])

    contextualized = sum(1 for r, c in zip(results, chunks, strict=False) if r != c.text)
    logger.info(f"Generated context for {contextualized}/{len(chunks)} chunks")

    return results


async def _refresh_session_token(session: Session, db) -> Session | None:
    """Refresh an expired access token using the refresh token."""
    from datetime import UTC, datetime, timedelta

    if not session.refresh_token:
        return None

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": session.refresh_token,
                "grant_type": "refresh_token",
            },
        )

        if token_response.status_code != 200:
            logger.warning(
                f"Failed to refresh token for session {session.id}: {token_response.text}"
            )
            return None

        tokens = token_response.json()
        new_access_token = tokens["access_token"]
        new_expires_at = datetime.now(UTC) + timedelta(seconds=tokens.get("expires_in", 3600))
        new_refresh_token = tokens.get("refresh_token", session.refresh_token)

        # Update session in database
        await db.execute(
            text("""
                UPDATE sessions
                SET access_token = :access_token,
                    refresh_token = :refresh_token,
                    expires_at = :expires_at
                WHERE id = :session_id
            """),
            {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "expires_at": new_expires_at,
                "session_id": str(session.id),
            },
        )
        await db.commit()

        # Return updated session
        session.access_token = new_access_token
        session.refresh_token = new_refresh_token
        session.expires_at = new_expires_at
        logger.info(f"Successfully refreshed token for session {session.id}")
        return session


async def _get_user_session_for_folder(folder_id: uuid.UUID) -> Session | None:
    """Get a valid user session for accessing files in a folder, refreshing if needed."""
    async with get_task_session() as db:
        # First try to get a non-expired session
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

        # No valid session found, try to get an expired one with a refresh token
        result = await db.execute(
            text("""
                SELECT s.id, s.user_id, s.access_token, s.refresh_token, s.expires_at
                FROM sessions s
                JOIN folders f ON f.user_id = s.user_id
                WHERE f.id = :folder_id
                  AND s.refresh_token IS NOT NULL
                ORDER BY s.expires_at DESC
                LIMIT 1
            """),
            {"folder_id": str(folder_id)},
        )
        row = result.first()
        if row:
            session = Session(
                id=row.id,
                user_id=row.user_id,
                access_token=row.access_token,
                refresh_token=row.refresh_token,
                expires_at=row.expires_at,
            )
            # Try to refresh the token
            refreshed = await _refresh_session_token(session, db)
            if refreshed:
                return refreshed

        return None


async def _get_file_info(file_id: uuid.UUID) -> File | None:
    """Get file information from the database."""
    async with get_task_session() as db:
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


async def _update_file_status(file_id: uuid.UUID, status: str) -> None:
    """Update file index status."""
    async with get_task_session() as db:
        await db.execute(
            text("UPDATE files SET index_status = :status WHERE id = :file_id"),
            {"status": status, "file_id": str(file_id)},
        )
        await db.commit()


async def _update_folder_progress(folder_id: uuid.UUID) -> None:
    """Update folder indexing progress."""
    async with get_task_session() as db:
        result = await db.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE index_status IN ('indexed', 'skipped')) as completed
                FROM files
                WHERE folder_id = :folder_id
            """),
            {"folder_id": str(folder_id)},
        )
        row = result.first()
        total = row.total if row else 0
        completed = row.completed if row else 0

        status = "ready" if completed == total else "indexing"
        await db.execute(
            text("""
                UPDATE folders
                SET files_indexed = :completed,
                    files_total = :total,
                    index_status = :status,
                    updated_at = NOW()
                WHERE id = :folder_id
            """),
            {
                "completed": completed,
                "total": total,
                "status": status,
                "folder_id": str(folder_id),
            },
        )
        await db.commit()


async def _process_job_async(file_id: str, folder_id: str, user_id: str) -> dict:
    """
    Async wrapper that runs all async work in a single event loop.

    Steps:
    1. Get user session for Google Drive access
    2. Download/export file content
    3. Extract text (type-specific)
    4. Generate file preview and embedding
    5. Chunk the content
    6. Generate chunk embeddings
    7. Store everything in database
    """
    # Validate UUIDs early - fail permanently on invalid IDs
    try:
        file_uuid = uuid.UUID(file_id)
        folder_uuid = uuid.UUID(folder_id)
        uuid.UUID(user_id)  # Validate but don't store
    except (ValueError, TypeError) as e:
        raise PermanentIndexingError(f"Invalid UUID parameter: {e}") from e

    logger.info(f"Processing file {file_id} in folder {folder_id}")

    # Get session for Drive access
    session = await _get_user_session_for_folder(folder_uuid)
    if not session:
        raise PermanentIndexingError(f"No valid session found for folder {folder_id}")

    # Get file info
    file_info = await _get_file_info(file_uuid)
    if not file_info:
        raise PermanentIndexingError(f"File {file_id} not found")

    # Initialize services
    drive = DriveService(session.access_token)
    extraction = ExtractionService()

    try:
        # Step 1: Download/export file content based on type
        if extraction.is_google_doc(file_info.mime_type):
            logger.info(f"Exporting Google Doc: {file_info.file_name}")
            html_content = await drive.export_google_doc(file_info.google_file_id)
            document = await extraction.extract_google_doc(html_content)
        elif extraction.is_pdf(file_info.mime_type):
            logger.info(f"Downloading PDF: {file_info.file_name}")
            pdf_content = await drive.download_file(file_info.google_file_id)
            document = await extraction.extract_pdf(pdf_content)
        elif extraction.is_vision_supported(file_info.mime_type):
            logger.info(f"Processing image with Vision: {file_info.file_name}")
            image_content = await drive.download_file(file_info.google_file_id)
            document = await extraction.extract_image(
                image_content, file_info.mime_type, file_info.file_name
            )
        else:
            # Skip unsupported file types gracefully
            logger.info(
                f"Skipping unsupported file type: {file_info.file_name} ({file_info.mime_type})"
            )
            await _update_file_status(file_uuid, "skipped")
            await _update_folder_progress(folder_uuid)
            return {"status": "skipped", "file_id": file_id, "chunks": 0}

        if not document.blocks:
            logger.warning(f"No content extracted from {file_info.file_name}")
            await _update_file_status(file_uuid, "indexed")
            await _update_folder_progress(folder_uuid)
            return {"status": "completed", "file_id": file_id, "chunks": 0}

        # Step 2: Generate file preview
        preview = generate_file_preview(document.blocks)
        logger.info(f"Generated preview ({len(preview)} chars)")

        # Step 3: Generate file-level embedding
        file_embedding = await embed_document(preview) if preview else None

        # Step 4: Chunk the document
        chunks = chunk_document(document.blocks)
        logger.info(f"Created {len(chunks)} chunks")

        if not chunks:
            await _update_file_status(file_uuid, "indexed")
            await _update_folder_progress(folder_uuid)
            return {"status": "completed", "file_id": file_id, "chunks": 0}

        # Step 5: Generate chunk texts (with optional context)
        if settings.contextual_chunking_enabled:
            full_document = "\n\n".join(b.text for b in document.blocks)
            chunk_texts = await _generate_chunk_contexts(
                file_name=file_info.file_name,
                full_document=full_document,
                chunks=chunks,
            )
        else:
            chunk_texts = [chunk.text for chunk in chunks]

        # Step 6: Generate chunk embeddings in batches
        chunk_embeddings = await embed_documents_batch(chunk_texts)

        # Step 7: Store everything in database
        async with get_task_session() as db:
            # Update file with preview and embedding
            await db.execute(
                text("""
                    UPDATE files
                    SET file_preview = :preview,
                        file_embedding = CAST(:embedding AS vector),
                        index_status = 'indexed'
                    WHERE id = :file_id
                """),
                {
                    "preview": preview,
                    "embedding": format_vector(file_embedding) if file_embedding else None,
                    "file_id": str(file_uuid),
                },
            )

            # Delete any existing chunks for this file (in case of re-indexing)
            await db.execute(
                text("DELETE FROM chunks WHERE file_id = :file_id"),
                {"file_id": str(file_uuid)},
            )

            # Insert chunks in a single batch operation
            if chunks:
                chunk_values = [
                    {
                        "id": str(uuid.uuid4()),
                        "file_id": str(file_uuid),
                        "user_id": user_id,
                        "chunk_text": chunk.text,
                        "chunk_embedding": format_vector(embedding),
                        "location": json.dumps(chunk.location),
                        "chunk_index": idx,
                    }
                    for idx, (chunk, embedding) in enumerate(
                        zip(chunks, chunk_embeddings, strict=False)
                    )
                ]
                await db.execute(
                    text("""
                        INSERT INTO chunks (id, file_id, user_id, chunk_text, chunk_embedding, location, chunk_index)
                        SELECT
                            (value->>'id')::uuid,
                            (value->>'file_id')::uuid,
                            (value->>'user_id')::uuid,
                            value->>'chunk_text',
                            CAST(value->>'chunk_embedding' AS vector),
                            (value->>'location')::jsonb,
                            (value->>'chunk_index')::int
                        FROM jsonb_array_elements(CAST(:values AS jsonb)) AS value
                    """),
                    {"values": json.dumps(chunk_values)},
                )

            await db.commit()

        # Update folder progress
        await _update_folder_progress(folder_uuid)

        logger.info(f"Successfully indexed {file_info.file_name} with {len(chunks)} chunks")
        return {"status": "completed", "file_id": file_id, "chunks": len(chunks)}

    except httpx.HTTPStatusError as e:
        # Handle permission denied (403) - skip without retry
        if e.response.status_code == 403:
            logger.warning(f"Permission denied for file {file_info.file_name}, marking as skipped")
            await _update_file_status(file_uuid, "skipped")
            await _update_folder_progress(folder_uuid)
            return {"status": "skipped", "file_id": file_id, "reason": "permission_denied"}
        # Other HTTP errors - treat as transient for retry
        raise TransientIndexingError(str(e)) from e
    except PERMANENT_ERRORS as e:
        # Convert to our exception type for proper retry handling
        raise PermanentIndexingError(str(e)) from e
    except TRANSIENT_ERRORS as e:
        # Convert to our exception type for proper retry handling
        raise TransientIndexingError(str(e)) from e


@celery_app.task(
    bind=True,
    autoretry_for=(TransientIndexingError,),
    retry_backoff=30,  # Start at 30 seconds
    retry_backoff_max=600,  # Cap at 10 minutes
    retry_jitter=True,
    max_retries=5,
    dont_autoretry_for=(PermanentIndexingError,),
    soft_time_limit=840,  # Raise SoftTimeLimitExceeded at 14 min
    time_limit=900,  # Hard kill after 15 min
)
def process_indexing_job(self, file_id: str, folder_id: str, user_id: str):
    """
    Process a single file indexing job.

    Uses single asyncio.run() call to preserve event loop efficiency.
    """
    self.update_state(state="PROGRESS", meta={"step": "starting", "file_id": file_id})

    try:
        # Single event loop for all async work
        result = asyncio.run(_process_job_async(file_id, folder_id, user_id))
        return result
    except PermanentIndexingError as e:
        logger.error(f"Permanent error processing file {file_id}: {e}")
        # Mark file as failed
        asyncio.run(_update_file_status(uuid.UUID(file_id), "failed"))
        raise
    except TransientIndexingError:
        # Will be retried by Celery
        raise
    except Exception as e:
        # Unexpected errors - wrap as transient to allow retry
        logger.error(f"Unexpected error processing file {file_id}: {e}")
        raise TransientIndexingError(str(e)) from e
