"""Agent tools package - exports tool definitions for agentic RAG.

These tools are only used when agent_mode=True is enabled.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tools.get_file import GET_FILE_TOOL
from app.services.tools.get_file_chunks import GET_FILE_CHUNKS_TOOL
from app.services.tools.search_folder import SEARCH_FOLDER_TOOL


class ToolName(StrEnum):
    """Enum for agent tool names."""

    SEARCH_FOLDER = "search_folder"
    GET_FILE_CHUNKS = "get_file_chunks"
    GET_FILE = "get_file"


@dataclass
class ToolContext:
    """Shared context passed to all tool executions."""

    db: AsyncSession
    folder_id: UUID
    user_id: UUID
    indexed_chunks: list  # Accumulates chunks for citation mapping


# All tools available to the agent
ALL_TOOLS = [SEARCH_FOLDER_TOOL, GET_FILE_CHUNKS_TOOL, GET_FILE_TOOL]

__all__ = [
    "ALL_TOOLS",
    "GET_FILE_CHUNKS_TOOL",
    "GET_FILE_TOOL",
    "SEARCH_FOLDER_TOOL",
    "ToolContext",
    "ToolName",
]
