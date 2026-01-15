"""Google Drive API service for file operations."""

from dataclasses import dataclass

import httpx


# Module-level HTTP client for connection reuse
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Get shared HTTP client for connection reuse."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


@dataclass
class FileMetadata:
    id: str
    name: str
    mime_type: str
    modified_time: str | None = None
    size: int | None = None


class DriveService:
    """Service for interacting with Google Drive API."""

    DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {"Authorization": f"Bearer {access_token}"}

    async def list_files(
        self, folder_id: str, page_token: str | None = None
    ) -> tuple[list[FileMetadata], str | None]:
        """List files in a folder."""
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, size)",
            "pageSize": 100,
        }
        if page_token:
            params["pageToken"] = page_token

        client = _get_http_client()
        response = await client.get(
            f"{self.DRIVE_API_BASE}/files",
            headers=self.headers,
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        files = [
            FileMetadata(
                id=f["id"],
                name=f["name"],
                mime_type=f["mimeType"],
                modified_time=f.get("modifiedTime"),
                size=f.get("size"),
            )
            for f in data.get("files", [])
        ]

        return files, data.get("nextPageToken")

    async def get_file_metadata(self, file_id: str) -> FileMetadata:
        """Get metadata for a single file."""
        client = _get_http_client()
        response = await client.get(
            f"{self.DRIVE_API_BASE}/files/{file_id}",
            headers=self.headers,
            params={"fields": "id, name, mimeType, modifiedTime, size"},
        )
        response.raise_for_status()
        f = response.json()

        return FileMetadata(
            id=f["id"],
            name=f["name"],
            mime_type=f["mimeType"],
            modified_time=f.get("modifiedTime"),
            size=f.get("size"),
        )

    async def export_google_doc(self, file_id: str, mime_type: str = "text/html") -> str:
        """Export a Google Doc to specified format."""
        client = _get_http_client()
        response = await client.get(
            f"{self.DRIVE_API_BASE}/files/{file_id}/export",
            headers=self.headers,
            params={"mimeType": mime_type},
        )
        response.raise_for_status()
        return response.text

    async def download_file(self, file_id: str) -> bytes:
        """Download a file's content."""
        client = _get_http_client()
        response = await client.get(
            f"{self.DRIVE_API_BASE}/files/{file_id}",
            headers=self.headers,
            params={"alt": "media"},
        )
        response.raise_for_status()
        return response.content
