"""Tool definitions for the agentic RAG system.

These tools are only used when agent_mode=True is enabled.

Note: Query refinement is handled by the agent's reasoning loop, not as a separate tool.
When search results are poor, the agent should simply call search_folder again with
a different query based on its analysis of what went wrong.
"""

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

GET_FILE_TOOL = {
    "name": "get_file",
    "description": """Download and extract the FULL raw content of a file directly from Google Drive.

Use this tool when:
- You need the complete, unprocessed document content
- The indexed chunks may have missed something
- You need to verify or cross-reference against the original source
- You need content that wasn't captured during indexing

This is SLOWER because it downloads fresh from Google Drive and extracts text.
Works with Google Docs and PDFs.""",
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

# All tools available to the agent
# Note: rewrite_query was removed - the agent handles query refinement through its reasoning
ALL_TOOLS = [SEARCH_FOLDER_TOOL, GET_FILE_CHUNKS_TOOL, GET_FILE_TOOL]
