"""Agentic RAG implementation with tool use.

This is the optional agent mode - more thorough but slower.
Uses Claude tool use for iterative search and query refinement.
"""

import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Conversation, Message
from app.services.anthropic import get_client
from app.services.posthog import LLMTimer, track_llm_generation, track_span
from app.services.tools import ALL_TOOLS, ToolContext, ToolName
from app.services.tools import get_file as get_file_tool
from app.services.tools import get_file_chunks as get_file_chunks_tool
from app.services.tools import search_folder as search_folder_tool

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
    ctx: ToolContext,
) -> str:
    """
    Execute an agent tool and return results.

    Dispatches to the appropriate tool module based on tool_name.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input parameters for the tool
        ctx: Tool context with db, folder_id, user_id, and indexed_chunks

    Returns:
        Tool execution result as a string
    """
    logger.info(f"[AGENT] Executing tool: {tool_name} with input: {tool_input}")

    match tool_name:
        case ToolName.SEARCH_FOLDER:
            return await search_folder_tool.execute(ctx, tool_input)
        case ToolName.GET_FILE_CHUNKS:
            return await get_file_chunks_tool.execute(ctx, tool_input)
        case ToolName.GET_FILE:
            return await get_file_tool.execute(ctx, tool_input)
        case _:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})


async def agentic_rag(
    db: AsyncSession,
    folder_id: uuid.UUID,
    user_id: uuid.UUID,
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

    # Create tool context for all tool executions
    tool_ctx = ToolContext(
        db=db,
        folder_id=folder_id,
        user_id=user_id,
        indexed_chunks=indexed_chunks,
    )

    client = get_client()
    iteration = 0
    response = None

    # Generate a trace ID to group all iterations in PostHog
    trace_id = str(uuid.uuid4())

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
        with LLMTimer() as timer:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=system_prompt,
                tools=ALL_TOOLS,
                messages=messages,
            )

        # Track LLM generation in PostHog
        track_llm_generation(
            distinct_id=str(user_id),
            model=settings.claude_model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=timer.elapsed_ms,
            trace_id=trace_id,
            properties={
                "mode": "agentic_rag",
                "iteration": iteration,
                "conversation_id": str(conversation.id),
            },
        )
        logger.info(f"[AGENT] Claude response stop_reason: {response.stop_reason}")

        # Check if model wants to use tools
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Executing tool: {block.name}")

                    # Emit tool status
                    tool_status = (
                        "searching" if block.name == ToolName.SEARCH_FOLDER else "processing"
                    )
                    if block.name in (ToolName.GET_FILE, ToolName.GET_FILE_CHUNKS):
                        tool_status = "reading_file"

                    yield f"data: {json.dumps({'agent_status': {'phase': tool_status, 'iteration': iteration, 'tool': block.name}})}\n\n"

                    # Execute tool and track span
                    with LLMTimer() as tool_timer:
                        result = await execute_tool(
                            block.name,
                            block.input,
                            tool_ctx,
                        )

                    # Track tool call span
                    track_span(
                        distinct_id=str(user_id),
                        trace_id=trace_id,
                        span_name=f"tool_{block.name}",
                        input_state=block.input,
                        output_state={"result_length": len(result)},
                        latency_ms=tool_timer.elapsed_ms,
                        properties={"iteration": iteration},
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
            with LLMTimer() as timer:
                synthesis_response = await client.messages.create(
                    model=settings.claude_model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=synthesis_messages,
                    # No tools - forces text response
                )

            # Track synthesis LLM generation in PostHog
            track_llm_generation(
                distinct_id=str(user_id),
                model=settings.claude_model,
                input_tokens=synthesis_response.usage.input_tokens,
                output_tokens=synthesis_response.usage.output_tokens,
                latency_ms=timer.elapsed_ms,
                trace_id=trace_id,
                properties={
                    "mode": "agentic_rag_synthesis",
                    "conversation_id": str(conversation.id),
                },
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
