"""Tool definitions for the agentic RAG system.

These tools are only used when agent_mode=True is enabled.
"""

SEARCH_FOLDER_TOOL = {
    "name": "search_folder",
    "description": """Search the user's indexed folder for relevant information using hybrid search (semantic + keyword).

Use this tool when:
- You need to find specific facts, quotes, or data
- The user asks about something that should be in their documents
- You need to verify information before answering

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

REWRITE_QUERY_TOOL = {
    "name": "rewrite_query",
    "description": """Reformulate a search query when initial results were poor.

Use this tool when:
- search_folder returned mostly irrelevant results
- You need to try a different angle or terminology
- The original query was too broad or too narrow

Provide feedback about what was wrong with the results to guide the rewrite.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "original_query": {
                "type": "string",
                "description": "The original search query that produced poor results",
            },
            "feedback": {
                "type": "string",
                "description": "What was wrong with the results (e.g., 'Got Q3 data but need Q4', 'Results were about marketing not engineering')",
            },
        },
        "required": ["original_query", "feedback"],
    },
}

GET_FILE_TOOL = {
    "name": "get_file",
    "description": """Retrieve the FULL indexed content of a specific file by fetching all its chunks.

Use this tool when:
- You need to see the complete document content
- Chunk excerpts are insufficient to answer the question
- You need to understand the full context or structure of a document
- You need to compare information across sections of the same document

Returns: Complete document text (all chunks concatenated) along with metadata.""",
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
ALL_TOOLS = [SEARCH_FOLDER_TOOL, REWRITE_QUERY_TOOL, GET_FILE_TOOL]
