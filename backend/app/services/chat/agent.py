"""Agentic RAG implementation with tool use.

This is the optional agent mode - more thorough but slower.
Uses Claude tool use for iterative search and query refinement.
"""

import base64
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Chunk, Conversation, File, Message, Session
from app.services.anthropic import get_client
from app.services.drive import DriveService
from app.services.file.extraction import ExtractionService
from app.services.hybrid_search import hybrid_search
from app.services.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 10


def build_agent_system_prompt(
    folder_name: str,
    files_indexed: int,
    files_total: int,
    max_iterations: int,
) -> str:
    """Build the agent system prompt with dynamic folder context."""
    return f"""You are a helpful assistant that answers questions based on the provided documents. You will be given a query or message about the folder and asked to respond.

## Folder Context
- **Folder**: {folder_name}
- **Indexed Files**: {files_indexed}/{files_total}
- **Iteration Limit**: You can search up to {max_iterations} times before synthesizing your answer

## Response Format
- **No fluff** - Skip intros like "Great! Let me compile..." - just answer directly
- Keep responses **short and scannable** - avoid walls of text
- Use **markdown headers** (## or ###) to organize sections

**When listing files or images:**
```
1. **[filename.ext](url)** - Brief title
   One-line description

2. **[filename.ext](url)** - Brief title
   One-line description
```

**When presenting data or comparisons**, use tables:
```
| Category | Value | Change |
|----------|-------|--------|
| Item 1   | $100M | +5%    |
| Item 2   | $50M  | -2%    |
```

**General rules:**
- Put links IN text, not floating separately
- One description line per item, not multiple paragraphs
- Add blank lines between sections
- Omit irrelevant results entirely

## Citations
- Use [N] notation **at the end of sections**, not scattered inline
- 2-4 citations per response max
- Combine like [1][2] when drawing from multiple sources

## Your Tools
- **search_folder**: Search for relevant information using hybrid search (semantic + keyword)
- **get_file_chunks**: Fast - retrieve all indexed chunks for a file (pre-processed content)
- **get_file**: Slower - download fresh content directly from Google Drive

## Workflow
1. Use search_folder to find relevant information
2. Evaluate results - if poor or incomplete, try different search terms
3. Use get_file_chunks for more context from a file (fast)
4. Use get_file only when you need fresh or full content from Drive (slower)
5. Synthesize your response with selective citations

## Search Quality Guidance
- Weighted score > 0.6: Results are likely relevant
- Weighted score 0.4-0.6: May need refinement
- Empty results: Try different terminology

## Guidelines
- Be thorough but efficient - don't over-search if you have good results
- Base answers ONLY on the context - don't make up information
- If you can't find relevant information, say so honestly"""


def format_location(location: dict) -> str:
    """Format chunk location into a human-readable string."""
    if not location:
        return "Document"
    if "page" in location:
        return f"Page {location['page']}"
    if "headings" in location and location["headings"]:
        return " > ".join(location["headings"])
    if "heading_path" in location and location["heading_path"]:
        return location["heading_path"]
    if "index" in location:
        return f"Section {location['index'] + 1}"
    return "Document"


def build_google_drive_url(google_file_id: str) -> str:
    """Build a Google Drive URL for a file."""
    return f"https://drive.google.com/file/d/{google_file_id}/view"


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
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.b64encode(image_content).decode("utf-8"),
                            },
                        },
                        {
                            "type": "text",
                            "text": f"This image is named '{file_name}'. Please describe this image in detail, including:\n"
                            "1. What the image shows (objects, people, scenes, diagrams, etc.)\n"
                            "2. Any text visible in the image (transcribe it)\n"
                            "3. Key visual details that might be relevant for search and retrieval\n"
                            "4. The overall context or purpose of the image if apparent",
                        },
                    ],
                }
            ],
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"[AGENT] Vision analysis failed for {file_name}: {e}")
        return f"[Image analysis failed: {str(e)}]"


async def get_user_session_for_folder(db: AsyncSession, folder_id: uuid.UUID) -> Session | None:
    """Get a valid user session for accessing files in a folder."""
    from sqlalchemy import text

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


def extract_citations_from_text(text: str, indexed_chunks: list) -> dict:
    """Extract numbered citations from agent response.

    Works like chat mode - finds [1], [2] etc and maps to the indexed_chunks list.
    """
    citations = {}

    # Find all [number] patterns in the text
    pattern = r"\[(\d+)\]"
    matches = re.findall(pattern, text)
    citation_numbers = {int(m) for m in matches}

    logger.info(f"[AGENT] Found citation numbers: {citation_numbers}")

    for num in citation_numbers:
        if 1 <= num <= len(indexed_chunks):
            chunk = indexed_chunks[num - 1]
            citations[str(num)] = {
                "chunk_id": str(chunk.get("chunk_id", "")),
                "file_name": chunk.get("file_name", ""),
                "location": chunk.get("location", "Document"),
                "excerpt": chunk.get("excerpt", ""),
                "google_drive_url": chunk.get("google_drive_url", ""),
            }
            logger.info(f"[AGENT] Mapped citation [{num}] -> {chunk.get('file_name')}")

    logger.info(f"[AGENT] Final citations count: {len(citations)}")
    return citations


async def execute_tool(
    tool_name: str,
    tool_input: dict,
    folder_id: uuid.UUID,
    db: AsyncSession,
    indexed_chunks: list,
) -> str:
    """
    Execute an agent tool and return results.

    Security: Validates folder ownership before file access.
    indexed_chunks: A list that accumulates all chunks found, numbered for citation.
    """
    logger.info(f"[AGENT] Executing tool: {tool_name} with input: {tool_input}")

    if tool_name == "search_folder":
        query = tool_input.get("query", "")
        if not query or not query.strip():
            logger.warning("[AGENT] Empty query provided to search_folder")
            return json.dumps({"error": "Empty query provided", "results": []})

        logger.info(f"[AGENT] Searching for: '{query}' in folder {folder_id}")

        try:
            # hybrid_search already calls embed_query internally
            results = await hybrid_search(
                db=db,
                query=query,
                folder_id=folder_id,
                top_k=15,
            )
            logger.info(f"[AGENT] Search returned {len(results)} results")
        except Exception as e:
            logger.error(f"[AGENT] Search failed: {e}", exc_info=True)
            return json.dumps({"error": f"Search failed: {str(e)}", "results": []})

        # Format results with source numbers like chat mode
        formatted_results = []
        for r in results[:10]:
            location = format_location(r.location)
            excerpt = r.chunk_text[:500] if len(r.chunk_text) > 500 else r.chunk_text

            # Add to indexed_chunks for citation mapping
            source_num = len(indexed_chunks) + 1
            indexed_chunks.append(
                {
                    "chunk_id": str(r.chunk_id),
                    "file_id": str(r.file_id),
                    "file_name": r.file_name,
                    "location": location,
                    "excerpt": excerpt[:200] + "..." if len(excerpt) > 200 else excerpt,
                    "google_drive_url": build_google_drive_url(r.google_file_id),
                }
            )

            # Format like chat mode: [N] From 'filename' (location): content
            formatted_results.append(
                f"[{source_num}] From '{r.file_name}' ({location}):\n{excerpt}"
            )

        if formatted_results:
            logger.info(f"[AGENT] Top result score: {results[0].weighted_score:.4f}")
        else:
            logger.warning("[AGENT] No search results found")

        return "\n\n---\n\n".join(formatted_results) if formatted_results else "No results found."

    elif tool_name == "get_file_chunks":
        # Fast: Return pre-indexed chunks
        file_id_str = tool_input.get("file_id", "")

        # Validate UUID format
        try:
            file_id = uuid.UUID(file_id_str)
        except (ValueError, TypeError):
            return json.dumps({"error": "Invalid file ID format"})

        # SECURITY: Verify file belongs to the folder (authorization check)
        result = await db.execute(
            select(File).where(
                File.id == file_id,
                File.folder_id == folder_id,  # Authorization check
            )
        )
        file = result.scalar_one_or_none()

        if not file:
            return json.dumps({"error": "File not found or access denied"})

        # Fetch all chunks for the file to get full content
        chunks_result = await db.execute(
            select(Chunk).where(Chunk.file_id == file_id).order_by(Chunk.chunk_index)
        )
        chunks = chunks_result.scalars().all()

        # Concatenate all chunk texts to get full document content
        if chunks:
            full_content = "\n\n".join(chunk.chunk_text for chunk in chunks)
        else:
            full_content = file.file_preview or "No content available"

        # Add to indexed_chunks for citation (use next number)
        source_num = len(indexed_chunks) + 1
        indexed_chunks.append(
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
            f"[AGENT] get_file_chunks returning {len(chunks)} chunks ({len(full_content)} chars) for {file.file_name} as [{source_num}]"
        )

        # Return formatted like chat mode
        return f"[{source_num}] Full content of '{file.file_name}':\n\n{full_content}"

    elif tool_name == "get_file":
        # Slower: Download fresh from Google Drive
        file_id_str = tool_input.get("file_id", "")

        # Validate UUID format
        try:
            file_id = uuid.UUID(file_id_str)
        except (ValueError, TypeError):
            return json.dumps({"error": "Invalid file ID format"})

        # SECURITY: Verify file belongs to the folder (authorization check)
        result = await db.execute(
            select(File).where(
                File.id == file_id,
                File.folder_id == folder_id,  # Authorization check
            )
        )
        file = result.scalar_one_or_none()

        if not file:
            return json.dumps({"error": "File not found or access denied"})

        # Get user session for Google Drive access
        session = await get_user_session_for_folder(db, folder_id)
        if not session:
            logger.error(f"[AGENT] No valid session found for folder {folder_id}")
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
                source_num = len(indexed_chunks) + 1
                indexed_chunks.append(
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
                    f"[AGENT] get_file analyzed image ({len(image_description)} chars) for {file.file_name} as [{source_num}]"
                )

                return (
                    f"[{source_num}] Image analysis of '{file.file_name}':\n\n{image_description}"
                )
            else:
                return json.dumps({"error": f"Unsupported file type: {file.mime_type}"})

            # Combine all text blocks
            full_content = "\n\n".join(block.text for block in document.blocks)

            # Add to indexed_chunks for citation
            source_num = len(indexed_chunks) + 1
            indexed_chunks.append(
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
                f"[AGENT] get_file downloaded fresh content ({len(full_content)} chars) for {file.file_name} as [{source_num}]"
            )

            # Return formatted like chat mode
            return f"[{source_num}] Full content of '{file.file_name}' (from Google Drive):\n\n{full_content}"

        except Exception as e:
            logger.error(f"[AGENT] Failed to download file {file.file_name}: {e}")
            return json.dumps({"error": f"Failed to download file: {str(e)}"})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


async def agentic_rag(
    db: AsyncSession,
    folder_id: uuid.UUID,
    conversation: Conversation,
    user_message: str,
    folder_name: str = "Documents",
    files_indexed: int = 0,
    files_total: int = 0,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> AsyncGenerator[str, None]:
    """
    Agentic RAG loop with tool use.

    This is the optional agent mode - uses Claude's tool use for iterative
    search and query refinement. More thorough but slower.

    Args:
        db: Database session
        folder_id: Folder to search within
        conversation: Conversation object for message storage
        user_message: User's query
        folder_name: Name of the folder for context
        files_indexed: Number of indexed files
        files_total: Total number of files
        max_iterations: Maximum number of tool-use iterations (default: 10)

    Yields:
        SSE-formatted chunks for streaming response
    """
    # Get conversation history
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    history_messages = history_result.scalars().all()

    # Build messages list
    messages = []
    for msg in history_messages:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    # Store user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)
    await db.commit()  # Explicit commit for streaming response

    # Track indexed chunks for citation extraction (numbered like chat mode)
    indexed_chunks: list = []
    client = get_client()
    iteration = 0
    response = None

    # Build dynamic system prompt with folder context
    system_prompt = build_agent_system_prompt(
        folder_name=folder_name,
        files_indexed=files_indexed,
        files_total=files_total,
        max_iterations=max_iterations,
    )

    # Agent loop
    while iteration < max_iterations:
        iteration += 1
        logger.info(f"Agent iteration {iteration} for query: {user_message[:50]}...")

        # Emit status update
        yield f"data: {json.dumps({'agent_status': {'phase': 'searching', 'iteration': iteration}})}\n\n"

        # Non-streaming call for tool use
        logger.info(f"[AGENT] Calling Claude API (iteration {iteration})")
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=system_prompt,
            tools=ALL_TOOLS,
            messages=messages,
        )
        logger.info(f"[AGENT] Claude response stop_reason: {response.stop_reason}")

        # Check if model wants to use tools
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Executing tool: {block.name}")

                    # Emit tool status
                    tool_status = "searching" if block.name == "search_folder" else "processing"
                    if block.name in ("get_file", "get_file_chunks"):
                        tool_status = "reading_file"

                    yield f"data: {json.dumps({'agent_status': {'phase': tool_status, 'iteration': iteration, 'tool': block.name}})}\n\n"

                    result = await execute_tool(
                        block.name,
                        block.input,
                        folder_id,
                        db,
                        indexed_chunks,
                    )
                    logger.info(f"[AGENT] Tool {block.name} result length: {len(result)} chars")
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            # Add assistant response and tool results to conversation
            logger.info(f"[AGENT] Adding {len(tool_results)} tool results to conversation")
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        else:
            # Model is done - exit loop
            break

    # Emit generating status
    yield f"data: {json.dumps({'agent_status': {'phase': 'generating'}})}\n\n"

    # Extract text from final response
    full_response = ""
    if response:
        for block in response.content:
            if hasattr(block, "text"):
                full_response += block.text

    logger.info(
        f"[AGENT] Final response length: {len(full_response)} chars, iterations: {iteration}"
    )
    logger.info(f"[AGENT] Indexed chunks: {len(indexed_chunks)}")

    # Get unique file names from indexed chunks
    searched_file_names = list({chunk.get("file_name", "") for chunk in indexed_chunks})

    # If we hit max iterations with tool_use, force a final synthesis
    if iteration >= max_iterations and response and response.stop_reason == "tool_use":
        logger.warning(f"[AGENT] Hit max iterations ({max_iterations}) - forcing final synthesis")

        # Build context summary from indexed chunks
        context_summary = "\n".join(
            [
                f"[{i + 1}] {chunk.get('file_name', '')}: {chunk.get('excerpt', '')[:100]}"
                for i, chunk in enumerate(indexed_chunks)
            ]
        )

        # Make final call WITHOUT tools to force synthesis
        synthesis_messages = messages.copy()
        synthesis_messages.append(
            {
                "role": "user",
                "content": f"""Based on all the search results you've gathered, please provide your final answer now.

Available sources:
{context_summary}

Remember to cite sources using [1], [2], etc. format. Synthesize the information you found.""",
            }
        )

        try:
            synthesis_response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=system_prompt,
                messages=synthesis_messages,
                # No tools - forces text response
            )
            full_response = ""
            for block in synthesis_response.content:
                if hasattr(block, "text"):
                    full_response += block.text
            logger.info(f"[AGENT] Forced synthesis response: {len(full_response)} chars")
        except Exception as e:
            logger.error(f"[AGENT] Synthesis call failed: {e}")
            full_response = "*I searched multiple times but couldn't complete the analysis. Please try rephrasing your question.*"

    # Stream the response to client
    for text in full_response:
        yield f"data: {json.dumps({'token': text})}\n\n"

    # Extract citations from the response (works like chat mode)
    citations = extract_citations_from_text(full_response, indexed_chunks)

    # Store assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=full_response,
        citations=citations,
    )
    db.add(assistant_msg)
    await db.commit()  # Explicit commit for streaming response

    # Send final message with metadata
    yield f"data: {json.dumps({'done': True, 'citations': citations, 'searched_files': searched_file_names, 'conversation_id': str(conversation.id), 'iterations': iteration})}\n\n"
