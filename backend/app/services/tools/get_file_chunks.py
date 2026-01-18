"""Get file chunks tool - definition and execution."""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models import Chunk, File
from app.utils import build_google_drive_url

if TYPE_CHECKING:
    from app.services.tools import ToolContext

logger = logging.getLogger(__name__)


GET_FILE_CHUNKS_TOOL = {
    "name": "get_file_chunks",
    "description": """Retrieve the indexed content of a specific file by fetching all its pre-processed chunks.

Use this tool when:
- You need to see more context from a file found in search results
- You want fast access to the indexed/chunked version of a document
- The search result excerpts are insufficient

This is FAST because it uses pre-indexed content. Returns all chunks concatenated.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "The UUID of the file to retrieve (from search results)",
            }
        },
        "required": ["file_id"],
    },
}


async def execute(ctx: ToolContext, tool_input: dict) -> str:
    """
    Execute the get_file_chunks tool.

    Fast retrieval of pre-indexed chunks for a file.

    Args:
        ctx: Tool context with db, folder_id, user_id, and indexed_chunks
        tool_input: Tool input containing the file_id

    Returns:
        Full content of the file from indexed chunks
    """
    file_id_str = tool_input.get("file_id", "")

    # Validate UUID format
    try:
        file_id = uuid.UUID(file_id_str)
    except (ValueError, TypeError):
        return json.dumps({"error": "Invalid file ID format"})

    # SECURITY: Verify file belongs to the folder (authorization check)
    result = await ctx.db.execute(
        select(File).where(
            File.id == file_id,
            File.folder_id == ctx.folder_id,
        )
    )
    file = result.scalar_one_or_none()

    if not file:
        return json.dumps({"error": "File not found or access denied"})

    # Fetch all chunks for the file to get full content
    chunks_result = await ctx.db.execute(
        select(Chunk).where(Chunk.file_id == file_id).order_by(Chunk.chunk_index)
    )
    chunks = chunks_result.scalars().all()

    # Concatenate all chunk texts to get full document content
    if chunks:
        full_content = "\n\n".join(chunk.chunk_text for chunk in chunks)
    else:
        full_content = file.file_preview or "No content available"

    # Add to indexed_chunks for citation (use next number)
    source_num = len(ctx.indexed_chunks) + 1
    ctx.indexed_chunks.append(
        {
            "chunk_id": "",
            "file_id": str(file.id),
            "file_name": file.file_name,
            "location": "Full document",
            "excerpt": (file.file_preview or "")[:200],
            "google_drive_url": build_google_drive_url(file.google_file_id),
        }
    )

    logger.info(
        f"[AGENT] get_file_chunks returning {len(chunks)} chunks "
        f"({len(full_content)} chars) for {file.file_name} as [{source_num}]"
    )

    return f"[{source_num}] Full content of '{file.file_name}':\n\n{full_content}"
