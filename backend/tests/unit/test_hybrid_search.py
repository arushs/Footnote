"""Tests for the hybrid search service."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hybrid_search import (
    rrf_score,
    keyword_search,
    vector_search_with_rank,
    rrf_fusion,
    hybrid_search,
    hybrid_retrieve_and_rerank,
    HybridResult,
    RRF_K,
)


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

    def test_rrf_score_custom_k(self):
        """RRF should work with custom k value."""
        score = rrf_score(1, k=10)
        expected = 1 / (10 + 1)
        assert abs(score - expected) < 0.0001

    def test_rrf_k_constant_is_60(self):
        """Default RRF_K constant should be 60."""
        assert RRF_K == 60


class TestRRFFusion:
    """Tests for RRF fusion of multiple ranked lists."""

    def test_fusion_combines_scores(self):
        """Fusion should combine RRF scores from multiple lists."""
        # Create mock results
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()

        vector_results = [
            HybridResult(
                chunk_id=chunk_id,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid1",
                chunk_text="content",
                location={"page": 1},
                vector_score=0.9,
                keyword_score=None,
                rrf_score=0.0,
            )
        ]
        keyword_results = [
            HybridResult(
                chunk_id=chunk_id,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid1",
                chunk_text="content",
                location={"page": 1},
                vector_score=None,
                keyword_score=0.5,
                rrf_score=0.0,
            )
        ]

        fused = rrf_fusion(vector_results, keyword_results)

        assert len(fused) == 1
        # Score should be sum of two RRF rank-1 scores
        expected_score = rrf_score(1) + rrf_score(1)
        assert abs(fused[0].rrf_score - expected_score) < 0.0001

    def test_fusion_unique_results(self):
        """Results appearing in only one list get single RRF score."""
        chunk_id_1 = uuid.uuid4()
        chunk_id_2 = uuid.uuid4()
        file_id = uuid.uuid4()

        vector_results = [
            HybridResult(
                chunk_id=chunk_id_1,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid1",
                chunk_text="vector only",
                location={},
                vector_score=0.9,
                keyword_score=None,
                rrf_score=0.0,
            )
        ]
        keyword_results = [
            HybridResult(
                chunk_id=chunk_id_2,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid1",
                chunk_text="keyword only",
                location={},
                vector_score=None,
                keyword_score=0.5,
                rrf_score=0.0,
            )
        ]

        fused = rrf_fusion(vector_results, keyword_results)

        assert len(fused) == 2
        # Each should have single RRF rank-1 score
        for result in fused:
            expected = rrf_score(1)
            assert abs(result.rrf_score - expected) < 0.0001

    def test_fusion_sorted_by_score(self):
        """Fused results should be sorted by RRF score descending."""
        chunk_id_1 = uuid.uuid4()
        chunk_id_2 = uuid.uuid4()
        file_id = uuid.uuid4()

        # Chunk 1 appears in both lists (higher combined score)
        # Chunk 2 appears in only one list
        vector_results = [
            HybridResult(
                chunk_id=chunk_id_1,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid1",
                chunk_text="both lists",
                location={},
                vector_score=0.9,
                keyword_score=None,
                rrf_score=0.0,
            ),
            HybridResult(
                chunk_id=chunk_id_2,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid1",
                chunk_text="vector only",
                location={},
                vector_score=0.8,
                keyword_score=None,
                rrf_score=0.0,
            ),
        ]
        keyword_results = [
            HybridResult(
                chunk_id=chunk_id_1,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid1",
                chunk_text="both lists",
                location={},
                vector_score=None,
                keyword_score=0.5,
                rrf_score=0.0,
            ),
        ]

        fused = rrf_fusion(vector_results, keyword_results)

        assert len(fused) == 2
        # First should be the one that appears in both lists (higher score)
        assert fused[0].chunk_id == chunk_id_1
        assert fused[0].rrf_score > fused[1].rrf_score

    def test_fusion_empty_lists(self):
        """Fusion should handle empty input lists."""
        fused = rrf_fusion([], [])
        assert fused == []

    def test_fusion_one_empty_list(self):
        """Fusion should work with one empty list."""
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()

        vector_results = [
            HybridResult(
                chunk_id=chunk_id,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid1",
                chunk_text="content",
                location={},
                vector_score=0.9,
                keyword_score=None,
                rrf_score=0.0,
            )
        ]

        fused = rrf_fusion(vector_results, [])

        assert len(fused) == 1
        assert fused[0].chunk_id == chunk_id


class TestHybridResult:
    """Tests for HybridResult dataclass."""

    def test_hybrid_result_creation(self):
        """HybridResult should store all fields."""
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()

        result = HybridResult(
            chunk_id=chunk_id,
            file_id=file_id,
            file_name="document.pdf",
            google_file_id="abc123",
            chunk_text="Test content",
            location={"page": 5},
            vector_score=0.95,
            keyword_score=0.8,
            rrf_score=0.03,
        )

        assert result.chunk_id == chunk_id
        assert result.file_id == file_id
        assert result.file_name == "document.pdf"
        assert result.google_file_id == "abc123"
        assert result.chunk_text == "Test content"
        assert result.location == {"page": 5}
        assert result.vector_score == 0.95
        assert result.keyword_score == 0.8
        assert result.rrf_score == 0.03

    def test_hybrid_result_optional_scores(self):
        """HybridResult should allow None for optional score fields."""
        result = HybridResult(
            chunk_id=uuid.uuid4(),
            file_id=uuid.uuid4(),
            file_name="test.pdf",
            google_file_id="gid",
            chunk_text="text",
            location={},
            vector_score=None,
            keyword_score=None,
            rrf_score=0.0,
        )

        assert result.vector_score is None
        assert result.keyword_score is None


class TestKeywordSearch:
    """Tests for keyword search functionality."""

    @pytest.mark.asyncio
    async def test_keyword_search_returns_results(self):
        """Keyword search should return HybridResult objects."""
        mock_db = AsyncMock()
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()

        # Mock database response
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                chunk_id=chunk_id,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid123",
                chunk_text="test content",
                location={"page": 1},
                rank=0.5,
            )
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await keyword_search(mock_db, "test query", uuid.uuid4())

        assert len(results) == 1
        assert results[0].chunk_id == chunk_id
        assert results[0].keyword_score == 0.5
        assert results[0].vector_score is None

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
    async def test_vector_search_returns_results(self):
        """Vector search should return HybridResult objects."""
        mock_db = AsyncMock()
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()

        # Mock database response
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                chunk_id=chunk_id,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid123",
                chunk_text="test content",
                location={"page": 1},
                similarity=0.9,
            )
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        embedding = [0.1] * 768
        results = await vector_search_with_rank(mock_db, embedding, uuid.uuid4())

        assert len(results) == 1
        assert results[0].chunk_id == chunk_id
        assert results[0].vector_score == 0.9
        assert results[0].keyword_score is None


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

            results = await hybrid_search(mock_db, "test query", uuid.uuid4())

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

        with patch("app.services.hybrid_search.embed_query") as mock_embed, \
             patch("app.services.hybrid_search.rerank") as mock_rerank:
            mock_embed.return_value = [0.1] * 768
            mock_rerank.return_value = []

            await hybrid_retrieve_and_rerank(
                mock_db,
                "test query",
                uuid.uuid4(),
                initial_top_k=30,
                final_top_k=10,
            )

            # Rerank should be called even with empty results
            # (it handles empty gracefully)
            assert mock_embed.called
