"""Tests for the hybrid search service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.hybrid_search import (
    RRF_K,
    HybridSearchResult,
    RetrievedChunk,
    build_or_query,
    format_vector,
    hybrid_retrieve_and_rerank,
    hybrid_search,
    keyword_search,
    rrf_score,
    vector_search_with_rank,
)


class TestFormatVector:
    """Tests for vector formatting."""

    def test_format_vector_basic(self):
        """Should format embedding list as PostgreSQL vector string."""
        embedding = [0.1, 0.2, 0.3]
        result = format_vector(embedding)
        assert result == "[0.1,0.2,0.3]"

    def test_format_vector_empty(self):
        """Should handle empty embedding list."""
        result = format_vector([])
        assert result == "[]"


class TestBuildOrQuery:
    """Tests for OR query building."""

    def test_build_or_query_basic(self):
        """Should convert query to OR-based format."""
        result = build_or_query("hello world test")
        assert result == "hello OR world OR test"

    def test_build_or_query_filters_short_words(self):
        """Should filter out words with 2 or fewer characters."""
        result = build_or_query("the a is and hello")
        assert result == "the OR and OR hello"

    def test_build_or_query_empty(self):
        """Should return original query if no valid words."""
        result = build_or_query("a b c")
        assert result == "a b c"


class TestRRFScore:
    """Tests for Reciprocal Rank Fusion scoring."""

    def test_rrf_score_rank_1(self):
        """RRF score for rank 1 should be 1/(k+1)."""
        score = rrf_score(1, k=60)
        expected = 1 / (60 + 1)
        assert abs(score - expected) < 0.0001

    def test_rrf_score_rank_10(self):
        """RRF score for rank 10 should be 1/(k+10)."""
        score = rrf_score(10, k=60)
        expected = 1 / (60 + 10)
        assert abs(score - expected) < 0.0001

    def test_rrf_score_higher_rank_lower_score(self):
        """Higher rank should produce lower RRF score."""
        score_rank_1 = rrf_score(1)
        score_rank_10 = rrf_score(10)
        assert score_rank_1 > score_rank_10

    def test_rrf_score_none_returns_zero(self):
        """None rank should return 0."""
        score = rrf_score(None)
        assert score == 0.0

    def test_rrf_score_custom_k(self):
        """RRF should work with custom k value."""
        score = rrf_score(1, k=10)
        expected = 1 / (10 + 1)
        assert abs(score - expected) < 0.0001

    def test_rrf_k_constant_is_60(self):
        """Default RRF_K constant should be 60."""
        assert RRF_K == 60


class TestHybridSearchResult:
    """Tests for HybridSearchResult dataclass."""

    def test_hybrid_result_creation(self):
        """HybridSearchResult should store all fields."""
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()

        result = HybridSearchResult(
            chunk_id=chunk_id,
            file_id=file_id,
            file_name="document.pdf",
            google_file_id="abc123",
            chunk_text="Test content",
            location={"page": 5},
            vector_rank=1,
            keyword_rank=2,
            rrf_score=0.03,
        )

        assert result.chunk_id == chunk_id
        assert result.file_id == file_id
        assert result.file_name == "document.pdf"
        assert result.google_file_id == "abc123"
        assert result.chunk_text == "Test content"
        assert result.location == {"page": 5}
        assert result.vector_rank == 1
        assert result.keyword_rank == 2
        assert result.rrf_score == 0.03

    def test_hybrid_result_optional_ranks(self):
        """HybridSearchResult should allow None for optional rank fields."""
        result = HybridSearchResult(
            chunk_id=uuid.uuid4(),
            file_id=uuid.uuid4(),
            file_name="test.pdf",
            google_file_id="gid",
            chunk_text="text",
            location={},
            vector_rank=None,
            keyword_rank=None,
            rrf_score=0.0,
        )

        assert result.vector_rank is None
        assert result.keyword_rank is None


class TestRetrievedChunk:
    """Tests for RetrievedChunk dataclass."""

    def test_retrieved_chunk_creation(self):
        """RetrievedChunk should store all fields."""
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()

        chunk = RetrievedChunk(
            chunk_id=chunk_id,
            file_id=file_id,
            file_name="document.pdf",
            google_file_id="abc123",
            chunk_text="Test content",
            location={"page": 5},
            similarity_score=0.95,
        )

        assert chunk.chunk_id == chunk_id
        assert chunk.file_id == file_id
        assert chunk.file_name == "document.pdf"
        assert chunk.similarity_score == 0.95


class TestKeywordSearch:
    """Tests for keyword search functionality."""

    @pytest.mark.asyncio
    async def test_keyword_search_returns_tuples(self):
        """Keyword search should return list of (chunk_id, rank) tuples."""
        mock_db = AsyncMock()
        chunk_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [MagicMock(chunk_id=chunk_id, rank=1)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await keyword_search(mock_db, "test query", uuid.uuid4())

        assert len(results) == 1
        assert results[0][0] == chunk_id
        assert results[0][1] == 1

    @pytest.mark.asyncio
    async def test_keyword_search_empty_results(self):
        """Keyword search should handle empty results."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await keyword_search(mock_db, "nonexistent query", uuid.uuid4())

        assert results == []


class TestVectorSearchWithRank:
    """Tests for vector search with rank."""

    @pytest.mark.asyncio
    async def test_vector_search_returns_tuples(self):
        """Vector search should return list of (chunk_id, rank, data) tuples."""
        mock_db = AsyncMock()
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                chunk_id=chunk_id,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid123",
                chunk_text="test content",
                location={"page": 1},
                rank=1,
            )
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        embedding = [0.1] * 768
        results = await vector_search_with_rank(mock_db, embedding, uuid.uuid4())

        assert len(results) == 1
        assert results[0][0] == chunk_id
        assert results[0][1] == 1
        assert results[0][2]["file_name"] == "test.pdf"


class TestHybridSearchIntegration:
    """Integration tests for the full hybrid search pipeline."""

    @pytest.mark.asyncio
    async def test_hybrid_search_calls_both_methods(self):
        """Hybrid search should call both keyword and vector search."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.hybrid_search.embed_query") as mock_embed:
            mock_embed.return_value = [0.1] * 768

            await hybrid_search(mock_db, "test query", uuid.uuid4())

            mock_embed.assert_called_once_with("test query")
            # Should have called execute twice (keyword + vector)
            assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_hybrid_retrieve_and_rerank_uses_reranker(self):
        """Hybrid retrieve and rerank should apply reranking."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("app.services.hybrid_search.embed_query") as mock_embed,
            patch("app.services.hybrid_search.rerank") as mock_rerank,
        ):
            mock_embed.return_value = [0.1] * 768
            mock_rerank.return_value = []

            await hybrid_retrieve_and_rerank(
                mock_db,
                "test query",
                uuid.uuid4(),
                initial_top_k=30,
                final_top_k=10,
            )

            assert mock_embed.called
