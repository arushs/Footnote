"""Get file tool - definition and execution."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import TYPE_CHECKING, cast

from anthropic.types import ImageBlockParam, TextBlockParam
from sqlalchemy import select

from app.config import settings
from app.models import File
from app.services.anthropic import get_client
from app.services.drive import DriveService
from app.services.file.extraction import ExtractionService
from app.utils import build_google_drive_url, get_user_session_for_folder

if TYPE_CHECKING:
    from app.services.tools import ToolContext

logger = logging.getLogger(__name__)

GET_FILE_TOOL = {
    "name": "get_file",
    "description": """Download and extract the FULL raw content of a file directly from Google Drive.

Use this tool when:
- You need the complete, unprocessed document content
- The indexed chunks may have missed something
- You need to verify or cross-reference against the original source
- You need content that wasn't captured during indexing
- You need to read a spreadsheet/Excel file (spreadsheets are only available via this tool)

This is SLOWER because it downloads fresh from Google Drive and extracts text.
Works with Google Docs, PDFs, images, and spreadsheets (Excel/Google Sheets).""",
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


async def _describe_image_with_vision(
    image_content: bytes,
    mime_type: str,
    file_name: str,
) -> str:
    """
    Use Claude's vision capability to describe an image.

    Args:
        image_content: Raw image bytes
        mime_type: Image MIME type (e.g., 'image/png')
        file_name: Name of the image file for context

    Returns:
        Text description of the image
    """
    client = get_client()

    # Normalize mime type for Claude API (it expects specific formats)
    media_type = mime_type
    if media_type == "image/jpg":
        media_type = "image/jpeg"

    try:
        image_block = cast(
            ImageBlockParam,
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.b64encode(image_content).decode("utf-8"),
                },
            },
        )
        text_block = cast(
            TextBlockParam,
            {
                "type": "text",
                "text": f"This image is named '{file_name}'. Please describe this image in detail, including:\n"
                "1. What the image shows (objects, people, scenes, diagrams, etc.)\n"
                "2. Any text visible in the image (transcribe it)\n"
                "3. Key visual details that might be relevant for search and retrieval\n"
                "4. The overall context or purpose of the image if apparent",
            },
        )
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=1000,
            messages=[{"role": "user", "content": [image_block, text_block]}],
        )
        if response.content and hasattr(response.content[0], "text"):
            return response.content[0].text
        return "[Image analysis returned no text]"
    except Exception as e:
        logger.error(f"[AGENT] Vision analysis failed for {file_name}: {e}")
        return f"[Image analysis failed: {str(e)}]"


async def execute(ctx: ToolContext, tool_input: dict) -> str:
    """
    Execute the get_file tool.

    Downloads fresh content from Google Drive and extracts text.

    Args:
        ctx: Tool context with db, folder_id, user_id, and indexed_chunks
        tool_input: Tool input containing the file_id

    Returns:
        Full content of the file from Google Drive
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

    # Get user session for Google Drive access
    session = await get_user_session_for_folder(ctx.db, ctx.folder_id)
    if not session:
        logger.error(f"[AGENT] No valid session found for folder {ctx.folder_id}")
        return json.dumps({"error": "No valid session - please re-authenticate"})

    try:
        # Initialize services
        drive = DriveService(session.access_token)
        extraction = ExtractionService()

        # Download and extract based on file type
        if extraction.is_google_doc(file.mime_type):
            logger.info(f"[AGENT] Exporting Google Doc: {file.file_name}")
            html_content = await drive.export_google_doc(file.google_file_id)
            document = await extraction.extract_google_doc(html_content)
        elif extraction.is_pdf(file.mime_type):
            logger.info(f"[AGENT] Downloading PDF: {file.file_name}")
            pdf_content = await drive.download_file(file.google_file_id)
            document = await extraction.extract_pdf(pdf_content)
        elif extraction.is_image(file.mime_type):
            # Use Claude vision to describe the image
            logger.info(f"[AGENT] Analyzing image with vision: {file.file_name}")
            image_content = await drive.download_file(file.google_file_id)
            image_description = await _describe_image_with_vision(
                image_content, file.mime_type, file.file_name
            )

            # Add to indexed_chunks for citation
            source_num = len(ctx.indexed_chunks) + 1
            ctx.indexed_chunks.append(
                {
                    "chunk_id": "",
                    "file_id": str(file.id),
                    "file_name": file.file_name,
                    "location": "Image analysis",
                    "excerpt": image_description[:200] if image_description else "",
                    "google_drive_url": build_google_drive_url(file.google_file_id),
                }
            )

            logger.info(
                f"[AGENT] get_file analyzed image ({len(image_description)} chars) "
                f"for {file.file_name} as [{source_num}]"
            )

            return f"[{source_num}] Image analysis of '{file.file_name}':\n\n{image_description}"
        elif extraction.is_spreadsheet(file.mime_type):
            # Download/export spreadsheet and extract as markdown tables
            logger.info(f"[AGENT] Downloading spreadsheet: {file.file_name}")
            if extraction.is_google_spreadsheet(file.mime_type):
                spreadsheet_content = await drive.export_google_sheet(file.google_file_id)
            else:
                spreadsheet_content = await drive.download_file(file.google_file_id)
            document = extraction.extract_spreadsheet(spreadsheet_content, file.file_name)

            # Combine all sheets into text
            full_content = "\n\n".join(block.text for block in document.blocks)

            # Add to indexed_chunks for citation
            source_num = len(ctx.indexed_chunks) + 1
            ctx.indexed_chunks.append(
                {
                    "chunk_id": "",
                    "file_id": str(file.id),
                    "file_name": file.file_name,
                    "location": "Full spreadsheet (Google Drive)",
                    "excerpt": full_content[:200] if full_content else "",
                    "google_drive_url": build_google_drive_url(file.google_file_id),
                }
            )

            logger.info(
                f"[AGENT] get_file downloaded spreadsheet ({len(full_content)} chars) "
                f"for {file.file_name} as [{source_num}]"
            )

            return (
                f"[{source_num}] Full content of spreadsheet '{file.file_name}':\n\n{full_content}"
            )
        else:
            return json.dumps({"error": f"Unsupported file type: {file.mime_type}"})

        # Combine all text blocks
        full_content = "\n\n".join(block.text for block in document.blocks)

        # Add to indexed_chunks for citation
        source_num = len(ctx.indexed_chunks) + 1
        ctx.indexed_chunks.append(
            {
                "chunk_id": "",
                "file_id": str(file.id),
                "file_name": file.file_name,
                "location": "Full document (Google Drive)",
                "excerpt": full_content[:200] if full_content else "",
                "google_drive_url": build_google_drive_url(file.google_file_id),
            }
        )

        logger.info(
            f"[AGENT] get_file downloaded fresh content ({len(full_content)} chars) "
            f"for {file.file_name} as [{source_num}]"
        )

        return f"[{source_num}] Full content of '{file.file_name}' (from Google Drive):\n\n{full_content}"

    except Exception as e:
        logger.error(f"[AGENT] Failed to download file {file.file_name}: {e}")
        return json.dumps({"error": f"Failed to download file: {str(e)}"})
