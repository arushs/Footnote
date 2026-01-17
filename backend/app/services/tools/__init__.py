"""Agent tools package - exports tool definitions for agentic RAG.

These tools are only used when agent_mode=True is enabled.

Note: Query refinement is handled by the agent's reasoning loop, not as a separate tool.
When search results are poor, the agent should simply call search_folder again with
a different query based on its analysis of what went wrong.
"""

from app.services.tools.get_file import GET_FILE_TOOL
from app.services.tools.get_file_chunks import GET_FILE_CHUNKS_TOOL
from app.services.tools.search_folder import SEARCH_FOLDER_TOOL

# All tools available to the agent
ALL_TOOLS = [SEARCH_FOLDER_TOOL, GET_FILE_CHUNKS_TOOL, GET_FILE_TOOL]

__all__ = [
    "ALL_TOOLS",
    "GET_FILE_CHUNKS_TOOL",
    "GET_FILE_TOOL",
    "SEARCH_FOLDER_TOOL",
]
