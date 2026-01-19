"""Test configuration and fixtures for integration tests."""

import os
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


# Define FileMetadata locally to avoid import issues
@dataclass
class MockFileMetadata:
    """Mock FileMetadata for testing without importing drive module."""

    id: str
    name: str
    mime_type: str
    modified_time: str | None = None
    size: int | None = None


# Override settings before importing app modules
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/footnote_test"
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"
os.environ["GOOGLE_REDIRECT_URI"] = "http://localhost:8000/api/auth/google/callback"
os.environ["FIREWORKS_API_KEY"] = "test-fireworks-key"
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
os.environ["MISTRAL_API_KEY"] = "test-mistral-key"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FRONTEND_URL"] = "http://localhost:3000"

from app.db import Base, get_db
from app.models import (
    Chunk,
    Conversation,
    File,
    Folder,
    IndexingJob,
    Message,
    Session,
    User,
)
from main import app

# Test database engine - use pool_pre_ping to handle stale connections
test_engine = create_async_engine(
    os.environ["DATABASE_URL"],
    echo=False,
    pool_pre_ping=True,
)
test_async_session = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    import asyncio

    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def setup_database():
    """Setup database schema once for the entire test session."""
    # Enable pgvector extension BEFORE creating tables (tables use vector type)
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Drop all tables after all tests complete
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test with clean data."""
    # Truncate all tables to start fresh for each test
    async with test_engine.begin() as conn:
        # Order matters due to foreign key constraints - truncate in reverse dependency order
        await conn.execute(
            text(
                "TRUNCATE messages, conversations, chunks, indexing_jobs, files, folders, sessions, users RESTART IDENTITY CASCADE"
            )
        )

    async with test_async_session() as session:
        yield session
        # No need for explicit cleanup - next test truncates


@pytest.fixture
async def override_db(db_session: AsyncSession):
    """Override the get_db dependency to use test database."""

    async def _get_test_db():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client(override_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        google_id="test-google-id-123",
        email="testuser@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_session(db_session: AsyncSession, test_user: User) -> Session:
    """Create a test session with valid tokens."""
    session = Session(
        id=uuid.uuid4(),
        user_id=test_user.id,
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.flush()
    return session


@pytest.fixture
async def expired_session(db_session: AsyncSession, test_user: User) -> Session:
    """Create an expired test session."""
    session = Session(
        id=uuid.uuid4(),
        user_id=test_user.id,
        access_token="expired-access-token",
        refresh_token="expired-refresh-token",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.flush()
    return session


@pytest.fixture
async def auth_client(client: AsyncClient, test_session: Session) -> AsyncClient:
    """Create an authenticated test client with session cookie."""
    client.cookies.set("session_id", str(test_session.id))
    return client


@pytest.fixture
async def test_folder(db_session: AsyncSession, test_user: User) -> Folder:
    """Create a test folder."""
    folder = Folder(
        id=uuid.uuid4(),
        user_id=test_user.id,
        google_folder_id="test-google-folder-id",
        folder_name="Test Folder",
        index_status="ready",
        files_total=2,
        files_indexed=2,
    )
    db_session.add(folder)
    await db_session.flush()
    return folder


@pytest.fixture
async def indexing_folder(db_session: AsyncSession, test_user: User) -> Folder:
    """Create a folder that is still indexing."""
    folder = Folder(
        id=uuid.uuid4(),
        user_id=test_user.id,
        google_folder_id="test-indexing-folder-id",
        folder_name="Indexing Folder",
        index_status="indexing",
        files_total=5,
        files_indexed=2,
    )
    db_session.add(folder)
    await db_session.flush()
    return folder


@pytest.fixture
async def test_file(db_session: AsyncSession, test_folder: Folder) -> File:
    """Create a test file with embedding."""
    file = File(
        id=uuid.uuid4(),
        folder_id=test_folder.id,
        google_file_id="test-google-file-id",
        file_name="test-document.pdf",
        mime_type="application/pdf",
        file_preview="This is a test document about machine learning.",
        index_status="indexed",
    )
    db_session.add(file)
    await db_session.flush()
    return file


@pytest.fixture
async def test_chunks(db_session: AsyncSession, test_file: File, test_user: User) -> list[Chunk]:
    """Create test chunks with embeddings."""
    chunks = []
    for i in range(3):
        chunk = Chunk(
            id=uuid.uuid4(),
            file_id=test_file.id,
            user_id=test_user.id,
            chunk_text=f"This is chunk {i + 1} containing test content about topic {i + 1}.",
            location={"page": i + 1, "headings": [f"Section {i + 1}"]},
            chunk_index=i,
        )
        db_session.add(chunk)
        chunks.append(chunk)

    await db_session.flush()

    # Insert embeddings using raw SQL (pgvector requires special handling)
    for chunk in chunks:
        # Create a dummy 768-dimensional embedding
        embedding = [0.1] * 768
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        await db_session.execute(
            text("""
                UPDATE chunks
                SET chunk_embedding = CAST(:embedding AS vector)
                WHERE id = :chunk_id
            """),
            {"embedding": embedding_str, "chunk_id": str(chunk.id)},
        )

    await db_session.flush()
    return chunks


@pytest.fixture
async def test_conversation(db_session: AsyncSession, test_folder: Folder) -> Conversation:
    """Create a test conversation."""
    conversation = Conversation(
        id=uuid.uuid4(),
        folder_id=test_folder.id,
    )
    db_session.add(conversation)
    await db_session.flush()
    return conversation


@pytest.fixture
async def test_messages(db_session: AsyncSession, test_conversation: Conversation) -> list[Message]:
    """Create test messages in a conversation."""
    messages = [
        Message(
            id=uuid.uuid4(),
            conversation_id=test_conversation.id,
            role="user",
            content="What is machine learning?",
        ),
        Message(
            id=uuid.uuid4(),
            conversation_id=test_conversation.id,
            role="assistant",
            content="Machine learning is a subset of AI that enables systems to learn from data. [1]",
            citations={
                "1": {
                    "chunk_id": str(uuid.uuid4()),
                    "file_name": "test-document.pdf",
                    "location": "Page 1",
                    "excerpt": "Machine learning is...",
                    "google_drive_url": "https://drive.google.com/file/d/test/view",
                }
            },
        ),
    ]
    for msg in messages:
        db_session.add(msg)
    await db_session.flush()
    return messages


@pytest.fixture
async def test_indexing_job(
    db_session: AsyncSession, test_folder: Folder, test_file: File
) -> IndexingJob:
    """Create a test indexing job."""
    job = IndexingJob(
        id=uuid.uuid4(),
        folder_id=test_folder.id,
        file_id=test_file.id,
        status="pending",
        priority=0,
        attempts=0,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.flush()
    return job


# Mock fixtures for external services


@pytest.fixture
def mock_google_oauth():
    """Mock Google OAuth token exchange and userinfo."""
    with patch("httpx.AsyncClient.post") as mock_post, patch("httpx.AsyncClient.get") as mock_get:
        # Mock token exchange response
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_token_response

        # Mock userinfo response
        mock_userinfo_response = MagicMock()
        mock_userinfo_response.status_code = 200
        mock_userinfo_response.json.return_value = {
            "id": "google-user-123",
            "email": "newuser@example.com",
        }
        mock_get.return_value = mock_userinfo_response

        yield {"post": mock_post, "get": mock_get}


@pytest.fixture
def mock_drive_service():
    """Mock Google Drive API responses."""
    with patch("app.services.drive.DriveService") as MockDriveService:
        mock_instance = MagicMock()
        MockDriveService.return_value = mock_instance

        # Mock list_files to return test file metadata
        async def mock_list_files(folder_id, page_token=None):
            files = [
                MockFileMetadata(
                    id="google-file-1",
                    name="Document 1.pdf",
                    mime_type="application/pdf",
                    modified_time=None,
                ),
                MockFileMetadata(
                    id="google-file-2",
                    name="Document 2.pdf",
                    mime_type="application/vnd.google-apps.document",
                    modified_time=None,
                ),
            ]
            return files, None

        mock_instance.list_files = AsyncMock(side_effect=mock_list_files)
        mock_instance.export_google_doc = AsyncMock(
            return_value="<html><body>Test content</body></html>"
        )
        mock_instance.download_file = AsyncMock(return_value=b"PDF content")

        yield mock_instance


@pytest.fixture
def mock_embedding_service():
    """Mock embedding and reranking services."""
    with (
        patch("app.services.file.embedding.embed_document") as mock_embed_document,
        patch("app.services.file.embedding.embed_query") as mock_embed_query,
        patch("app.services.file.embedding.embed_documents_batch") as mock_embed_batch,
        patch("app.services.file.embedding.rerank") as mock_rerank,
    ):
        # Return 768-dimensional dummy embeddings
        mock_embed_document.return_value = [0.1] * 768
        mock_embed_query.return_value = [0.1] * 768
        mock_embed_batch.return_value = [[0.1] * 768 for _ in range(10)]

        # Return reranked indices with scores
        mock_rerank.return_value = [(0, 0.95), (1, 0.85), (2, 0.75)]

        yield {
            "embed_document": mock_embed_document,
            "embed_query": mock_embed_query,
            "embed_documents_batch": mock_embed_batch,
            "rerank": mock_rerank,
        }


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic Claude API for chat responses."""
    mock_client = MagicMock()

    class MockUsage:
        input_tokens = 100
        output_tokens = 50

    class MockFinalMessage:
        usage = MockUsage()

    # Create a mock stream that yields tokens
    class MockStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @property
        def text_stream(self):
            async def gen():
                for token in ["This ", "is ", "a ", "test ", "response. ", "[1]"]:
                    yield token

            return gen()

        async def get_final_message(self):
            return MockFinalMessage()

    mock_client.messages.stream.return_value = MockStream()

    yield mock_client


@pytest.fixture
def mock_extraction_service():
    """Mock text extraction service."""
    with patch("app.services.file.extraction.ExtractionService") as MockExtraction:
        from app.services.file.extraction import ExtractedDocument, TextBlock

        mock_instance = MagicMock()
        MockExtraction.return_value = mock_instance

        mock_instance.is_google_doc.return_value = True
        mock_instance.is_pdf.return_value = False
        mock_instance.is_supported.return_value = True

        async def mock_extract_google_doc(html):
            return ExtractedDocument(
                title="Test Document",
                blocks=[
                    TextBlock(
                        text="This is paragraph 1 about machine learning.",
                        location={"element_type": "paragraph", "index": 0},
                        heading_context="Introduction",
                    ),
                    TextBlock(
                        text="This is paragraph 2 with more content.",
                        location={"element_type": "paragraph", "index": 1},
                        heading_context="Introduction",
                    ),
                ],
                metadata={},
            )

        mock_instance.extract_google_doc = AsyncMock(side_effect=mock_extract_google_doc)

        yield mock_instance
