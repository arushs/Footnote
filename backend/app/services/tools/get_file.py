"""Get file tool definition."""

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
