"""Search folder tool definition."""

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
