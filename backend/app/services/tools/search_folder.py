"""Search folder tool - definition and execution."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from app.services.hybrid_search import hybrid_search
from app.utils import build_google_drive_url, format_location

if TYPE_CHECKING:
    from app.services.tools import ToolContext

logger = logging.getLogger(__name__)


SEARCH_FOLDER_TOOL = {
    "name": "search_folder",
    "description": """Search the user's indexed folder for relevant information using hybrid search (semantic + keyword).

Use this tool when:
- You need to find specific facts, quotes, or data
- The user asks about something that should be in their documents
- You need to verify information before answering
- Previous search results were poor and you want to try different terms

If results are poor, analyze what's missing and search again with:
- Different terminology or synonyms
- Broader or more specific terms
- Alternative angles on the topic

Returns: List of relevant document chunks with file names and relevance scores.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query - be specific. Include relevant terms, dates, names, or concepts.",
            }
        },
        "required": ["query"],
    },
}


async def execute(ctx: ToolContext, tool_input: dict) -> str:
    """
    Execute the search_folder tool.

    Args:
        ctx: Tool context with db, folder_id, user_id, and indexed_chunks
        tool_input: Tool input containing the query

    Returns:
        Formatted search results or error message
    """
    query = tool_input.get("query", "")
    if not query or not query.strip():
        logger.warning("[AGENT] Empty query provided to search_folder")
        return json.dumps({"error": "Empty query provided", "results": []})

    logger.info(f"[AGENT] Searching for: '{query}' in folder {ctx.folder_id}")

    try:
        results = await hybrid_search(
            db=ctx.db,
            query=query,
            folder_id=ctx.folder_id,
            user_id=ctx.user_id,
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
        source_num = len(ctx.indexed_chunks) + 1
        ctx.indexed_chunks.append(
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
        formatted_results.append(f"[{source_num}] From '{r.file_name}' ({location}):\n{excerpt}")

    if formatted_results:
        logger.info(f"[AGENT] Top result score: {results[0].weighted_score:.4f}")
    else:
        logger.warning("[AGENT] No search results found")

    return "\n\n---\n\n".join(formatted_results) if formatted_results else "No results found."
