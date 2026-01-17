"""Get file chunks tool definition."""

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
