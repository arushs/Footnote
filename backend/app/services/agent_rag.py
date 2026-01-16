"""Agentic RAG implementation with tool use.

This is the optional agent mode - more thorough but slower.
Uses Claude tool use for iterative search and query refinement.
"""

import json
import logging
import re
import uuid
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Conversation, File, Message
from app.services.agent_tools import ALL_TOOLS
from app.services.anthropic import get_client
from app.services.embedding import embed_query
from app.services.hybrid_search import hybrid_search

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3

AGENT_SYSTEM_PROMPT = """You are a helpful assistant with access to the user's Google Drive folder documents.

## Your Tools
- **search_folder**: Search for relevant information using hybrid search
- **rewrite_query**: Reformulate queries when search results are poor
- **get_file**: Retrieve full document content when needed

## Workflow
1. When the user asks a question, use search_folder to find relevant information
2. Evaluate if the results are sufficient (look at relevance scores and content)
3. If results are poor, use rewrite_query and search again (max 3 total searches)
4. Use get_file only when you need broader context from a specific document
5. Generate your response with inline citations [filename]

## Guidelines
- Be thorough but efficient - don't over-search if you have good results
- Cite your sources using [filename] format
- If you can't find relevant information after trying, say so honestly
- Maximum 3 search attempts before responding with best available information"""


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


def extract_citations_from_text(text: str, searched_files: dict) -> dict:
    """Extract [filename] citations from agent response."""
    citations = {}
    # Match [filename] pattern - capture text between brackets
    pattern = r"\[([^\]]+)\]"
    matches = re.findall(pattern, text)

    for i, match in enumerate(matches, 1):
        # Check if this looks like a filename (not a number citation)
        if not match.isdigit() and match in searched_files:
            file_info = searched_files[match]
            citations[str(i)] = {
                "chunk_id": str(file_info.get("chunk_id", "")),
                "file_name": match,
                "location": file_info.get("location", "Document"),
                "excerpt": file_info.get("excerpt", ""),
                "google_drive_url": file_info.get("google_drive_url", ""),
            }

    return citations


async def execute_tool(
    tool_name: str,
    tool_input: dict,
    folder_id: uuid.UUID,
    db: AsyncSession,
    searched_files: dict,
) -> str:
    """
    Execute an agent tool and return results.

    Security: Validates folder ownership before file access.
    """
    if tool_name == "search_folder":
        query = tool_input.get("query", "")
        if not query or not query.strip():
            return json.dumps({"error": "Empty query provided", "chunks": []})

        query_embedding = await embed_query(query)
        results = await hybrid_search(
            db=db,
            query=query,
            folder_id=folder_id,
            top_k=15,
        )

        chunks_data = []
        for r in results[:10]:
            location = format_location(r.location)
            excerpt = r.chunk_text[:500] if len(r.chunk_text) > 500 else r.chunk_text

            # Track searched files for citation extraction later
            if r.file_name not in searched_files:
                searched_files[r.file_name] = {
                    "chunk_id": r.chunk_id,
                    "file_id": r.file_id,
                    "location": location,
                    "excerpt": excerpt[:200] + "..." if len(excerpt) > 200 else excerpt,
                    "google_drive_url": build_google_drive_url(r.google_file_id),
                }

            chunks_data.append({
                "file_id": str(r.file_id),
                "file_name": r.file_name,
                "content": excerpt,
                "location": location,
                "score": round(r.rrf_score, 4),
            })

        return json.dumps({
            "chunks": chunks_data,
            "total_found": len(results),
        })

    elif tool_name == "rewrite_query":
        # Use a fast model to rewrite the query
        client = get_client()
        rewrite_response = await client.messages.create(
            model="claude-haiku-4-20250514",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"""Rewrite this search query for better document retrieval.

Original query: {tool_input.get('original_query', '')}
Problem with results: {tool_input.get('feedback', '')}

Return ONLY the rewritten query, nothing else."""
            }]
        )
        return rewrite_response.content[0].text.strip()

    elif tool_name == "get_file":
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

        # Track file for citation extraction
        if file.file_name not in searched_files:
            searched_files[file.file_name] = {
                "chunk_id": "",
                "file_id": file.id,
                "location": "Full document",
                "excerpt": (file.file_preview or "")[:200],
                "google_drive_url": build_google_drive_url(file.google_file_id),
            }

        return json.dumps({
            "file_name": file.file_name,
            "content": file.file_preview or "No preview available",
            "mime_type": file.mime_type,
        })

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


async def agentic_rag(
    db: AsyncSession,
    folder_id: uuid.UUID,
    conversation: Conversation,
    user_message: str,
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
    await db.flush()

    # Track searched files for citation extraction
    searched_files: dict = {}
    client = get_client()
    iteration = 0
    response = None

    # Agent loop
    while iteration < MAX_ITERATIONS:
        iteration += 1
        logger.info(f"Agent iteration {iteration} for query: {user_message[:50]}...")

        # Emit status update
        yield f'data: {json.dumps({"agent_status": {"phase": "searching", "iteration": iteration}})}\n\n'

        # Non-streaming call for tool use
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=AGENT_SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            messages=messages,
        )

        # Check if model wants to use tools
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Executing tool: {block.name}")

                    # Emit tool status
                    tool_status = "searching" if block.name == "search_folder" else "processing"
                    if block.name == "rewrite_query":
                        tool_status = "rewriting"
                    elif block.name == "get_file":
                        tool_status = "reading_file"

                    yield f'data: {json.dumps({"agent_status": {"phase": tool_status, "iteration": iteration, "tool": block.name}})}\n\n'

                    result = await execute_tool(
                        block.name,
                        block.input,
                        folder_id,
                        db,
                        searched_files,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Add assistant response and tool results to conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        else:
            # Model is done - exit loop
            break

    # Emit generating status
    yield f'data: {json.dumps({"agent_status": {"phase": "generating"}})}\n\n'

    # Extract text from final response
    full_response = ""
    if response:
        for block in response.content:
            if hasattr(block, "text"):
                full_response += block.text

    # Add note if we hit max iterations
    if iteration >= MAX_ITERATIONS and response and response.stop_reason == "tool_use":
        full_response += "\n\n*Note: I searched multiple times but found limited relevant information. The answer above is based on the best available results.*"

    # Stream the response to client
    for text in full_response:
        yield f'data: {json.dumps({"token": text})}\n\n'

    # Extract citations from the response
    citations = extract_citations_from_text(full_response, searched_files)

    # Store assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=full_response,
        citations=citations,
    )
    db.add(assistant_msg)
    await db.flush()

    # Send final message with metadata
    yield f'data: {json.dumps({"done": True, "citations": citations, "searched_files": list(searched_files.keys()), "conversation_id": str(conversation.id), "iterations": iteration})}\n\n'
