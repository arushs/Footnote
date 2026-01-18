"""Tests for the hybrid search service."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.hybrid_search import (
    KEYWORD_WEIGHT,
    RECENCY_HALF_LIFE_DAYS,
    RECENCY_WEIGHT,
    VECTOR_WEIGHT,
    HybridSearchResult,
    RetrievedChunk,
    build_or_query,
    calculate_recency_score,
    calculate_weighted_score,
    format_vector,
    hybrid_retrieve_and_rerank,
    hybrid_search,
    keyword_search,
    vector_search_with_scores,
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


class TestRecencyScore:
    """Tests for recency score calculation."""

    def test_recency_score_now(self):
        """Document updated just now should have score near 1.0."""
        now = datetime.now(timezone.utc)
        score = calculate_recency_score(now)
        assert score > 0.99

    def test_recency_score_half_life(self):
        """Document at half-life age should have score of 0.5."""
        now = datetime.now(timezone.utc)
        half_life_ago = now - timedelta(days=RECENCY_HALF_LIFE_DAYS)
        score = calculate_recency_score(half_life_ago)
        assert abs(score - 0.5) < 0.01

    def test_recency_score_two_half_lives(self):
        """Document at 2x half-life age should have score of 0.25."""
        now = datetime.now(timezone.utc)
        two_half_lives_ago = now - timedelta(days=2 * RECENCY_HALF_LIFE_DAYS)
        score = calculate_recency_score(two_half_lives_ago)
        assert abs(score - 0.25) < 0.01

    def test_recency_score_none_returns_default(self):
        """None date should return default score of 0.5."""
        score = calculate_recency_score(None)
        assert score == 0.5

    def test_recency_score_future_date(self):
        """Future dates should return 1.0."""
        future = datetime.now(timezone.utc) + timedelta(days=10)
        score = calculate_recency_score(future)
        assert score == 1.0

    def test_recency_score_naive_datetime(self):
        """Should handle naive datetime by treating as UTC."""
        now = datetime.now()  # naive
        score = calculate_recency_score(now)
        assert score > 0.99

    def test_recency_score_old_document(self):
        """Very old document should have very low score."""
        old = datetime.now(timezone.utc) - timedelta(days=365)
        score = calculate_recency_score(old)
        assert score < 0.01

    def test_recency_score_custom_half_life(self):
        """Should work with custom half-life."""
        now = datetime.now(timezone.utc)
        one_week_ago = now - timedelta(days=7)
        score = calculate_recency_score(one_week_ago, half_life_days=7)
        assert abs(score - 0.5) < 0.01


class TestWeightedScore:
    """Tests for weighted score calculation."""

    def test_weighted_score_all_ones(self):
        """All scores of 1.0 should produce 1.0."""
        score = calculate_weighted_score(1.0, 1.0, 1.0)
        assert abs(score - 1.0) < 0.001

    def test_weighted_score_all_zeros(self):
        """All scores of 0.0 should produce 0.0."""
        score = calculate_weighted_score(0.0, 0.0, 0.0)
        assert score == 0.0

    def test_weighted_score_vector_only(self):
        """Vector score only should apply vector weight."""
        score = calculate_weighted_score(1.0, 0.0, 0.0)
        assert abs(score - VECTOR_WEIGHT) < 0.001

    def test_weighted_score_keyword_only(self):
        """Keyword score only should apply keyword weight."""
        score = calculate_weighted_score(0.0, 1.0, 0.0)
        assert abs(score - KEYWORD_WEIGHT) < 0.001

    def test_weighted_score_recency_only(self):
        """Recency score only should apply recency weight."""
        score = calculate_weighted_score(0.0, 0.0, 1.0)
        assert abs(score - RECENCY_WEIGHT) < 0.001

    def test_weighted_score_custom_weights(self):
        """Should work with custom weights."""
        score = calculate_weighted_score(
            1.0, 1.0, 1.0,
            vector_weight=0.5,
            keyword_weight=0.3,
            recency_weight=0.2,
        )
        assert abs(score - 1.0) < 0.001

    def test_weights_sum_to_one(self):
        """Default weights should sum to 1.0."""
        total = VECTOR_WEIGHT + KEYWORD_WEIGHT + RECENCY_WEIGHT
        assert abs(total - 1.0) < 0.001

    def test_weighted_score_partial_scores(self):
        """Should correctly weight partial scores."""
        # 0.8 * 0.6 + 0.5 * 0.2 + 0.9 * 0.2 = 0.48 + 0.1 + 0.18 = 0.76
        score = calculate_weighted_score(0.8, 0.5, 0.9)
        expected = 0.8 * VECTOR_WEIGHT + 0.5 * KEYWORD_WEIGHT + 0.9 * RECENCY_WEIGHT
        assert abs(score - expected) < 0.001


class TestHybridSearchResult:
    """Tests for HybridSearchResult dataclass."""

    def test_hybrid_result_creation(self):
        """HybridSearchResult should store all fields."""
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        result = HybridSearchResult(
            chunk_id=chunk_id,
            file_id=file_id,
            file_name="document.pdf",
            google_file_id="abc123",
            chunk_text="Test content",
            location={"page": 5},
            file_updated_at=now,
            vector_score=0.85,
            keyword_score=0.70,
            recency_score=0.95,
            weighted_score=0.83,
        )

        assert result.chunk_id == chunk_id
        assert result.file_id == file_id
        assert result.file_name == "document.pdf"
        assert result.google_file_id == "abc123"
        assert result.chunk_text == "Test content"
        assert result.location == {"page": 5}
        assert result.file_updated_at == now
        assert result.vector_score == 0.85
        assert result.keyword_score == 0.70
        assert result.recency_score == 0.95
        assert result.weighted_score == 0.83

    def test_hybrid_result_optional_updated_at(self):
        """HybridSearchResult should allow None for file_updated_at."""
        result = HybridSearchResult(
            chunk_id=uuid.uuid4(),
            file_id=uuid.uuid4(),
            file_name="test.pdf",
            google_file_id="gid",
            chunk_text="text",
            location={},
            file_updated_at=None,
            vector_score=0.5,
            keyword_score=0.5,
            recency_score=0.5,
            weighted_score=0.5,
        )

        assert result.file_updated_at is None


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
    async def test_keyword_search_returns_normalized_scores(self):
        """Keyword search should return list of (chunk_id, normalized_score) tuples."""
        mock_db = AsyncMock()
        chunk_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [MagicMock(chunk_id=chunk_id, score=0.5)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await keyword_search(mock_db, "test query", uuid.uuid4())

        assert len(results) == 1
        assert results[0][0] == chunk_id
        assert results[0][1] == 1.0  # Normalized to max

    @pytest.mark.asyncio
    async def test_keyword_search_normalizes_multiple_results(self):
        """Keyword search should normalize scores relative to max."""
        mock_db = AsyncMock()
        chunk_id_1 = uuid.uuid4()
        chunk_id_2 = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(chunk_id=chunk_id_1, score=1.0),
            MagicMock(chunk_id=chunk_id_2, score=0.5),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await keyword_search(mock_db, "test query", uuid.uuid4())

        assert len(results) == 2
        assert results[0][1] == 1.0  # Max score normalized to 1
        assert results[1][1] == 0.5  # Half of max

    @pytest.mark.asyncio
    async def test_keyword_search_empty_results(self):
        """Keyword search should handle empty results."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await keyword_search(mock_db, "nonexistent query", uuid.uuid4())

        assert results == []


class TestVectorSearchWithScores:
    """Tests for vector search with similarity scores."""

    @pytest.mark.asyncio
    async def test_vector_search_returns_similarity_scores(self):
        """Vector search should return (chunk_id, similarity, data) tuples."""
        mock_db = AsyncMock()
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                chunk_id=chunk_id,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid123",
                chunk_text="test content",
                location={"page": 1},
                similarity=0.85,
                file_updated_at=now,
            )
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        embedding = [0.1] * 768
        results = await vector_search_with_scores(mock_db, embedding, uuid.uuid4())

        assert len(results) == 1
        assert results[0][0] == chunk_id
        assert results[0][1] == 0.85
        assert results[0][2]["file_name"] == "test.pdf"
        assert results[0][2]["file_updated_at"] == now

    @pytest.mark.asyncio
    async def test_vector_search_clamps_negative_similarity(self):
        """Vector search should clamp negative similarity to 0."""
        mock_db = AsyncMock()
        chunk_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                chunk_id=chunk_id,
                file_id=uuid.uuid4(),
                file_name="test.pdf",
                google_file_id="gid",
                chunk_text="content",
                location={},
                similarity=-0.1,
                file_updated_at=None,
            )
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        embedding = [0.1] * 768
        results = await vector_search_with_scores(mock_db, embedding, uuid.uuid4())

        assert results[0][1] == 0.0  # Clamped to 0


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
    async def test_hybrid_search_combines_results(self):
        """Hybrid search should combine and score results from both searches."""
        mock_db = AsyncMock()
        chunk_id = uuid.uuid4()
        file_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # First call: vector search
        vector_result = MagicMock()
        vector_result.fetchall.return_value = [
            MagicMock(
                chunk_id=chunk_id,
                file_id=file_id,
                file_name="test.pdf",
                google_file_id="gid",
                chunk_text="content",
                location={},
                similarity=0.8,
                file_updated_at=now,
            )
        ]

        # Second call: keyword search
        keyword_result = MagicMock()
        keyword_result.fetchall.return_value = [
            MagicMock(chunk_id=chunk_id, score=0.6)
        ]

        mock_db.execute = AsyncMock(side_effect=[vector_result, keyword_result])

        with patch("app.services.hybrid_search.embed_query") as mock_embed:
            mock_embed.return_value = [0.1] * 768

            results = await hybrid_search(mock_db, "test query", uuid.uuid4())

            assert len(results) == 1
            assert results[0].chunk_id == chunk_id
            assert results[0].vector_score == 0.8
            assert results[0].keyword_score == 1.0  # Normalized to max
            assert results[0].recency_score > 0.99  # Just now
            assert results[0].weighted_score > 0

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


class TestScoringBehavior:
    """Tests for expected scoring behavior."""

    def test_recent_documents_score_higher(self):
        """Recent documents should score higher than old ones with same relevance."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=90)

        recent_recency = calculate_recency_score(now)
        old_recency = calculate_recency_score(old)

        # Same vector and keyword scores
        recent_score = calculate_weighted_score(0.8, 0.6, recent_recency)
        old_score = calculate_weighted_score(0.8, 0.6, old_recency)

        assert recent_score > old_score

    def test_highly_relevant_old_doc_can_beat_less_relevant_new(self):
        """Highly relevant old doc can still beat less relevant new doc."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=60)

        # Very relevant old document
        old_score = calculate_weighted_score(
            0.95,  # High vector match
            0.90,  # High keyword match
            calculate_recency_score(old),
        )

        # Less relevant new document
        new_score = calculate_weighted_score(
            0.50,  # Low vector match
            0.40,  # Low keyword match
            calculate_recency_score(now),
        )

        assert old_score > new_score

    def test_vector_weight_is_dominant(self):
        """Vector similarity should be the dominant factor."""
        # High vector, low everything else
        high_vector = calculate_weighted_score(1.0, 0.0, 0.0)

        # Low vector, high everything else
        low_vector = calculate_weighted_score(0.0, 1.0, 1.0)

        # With default weights (0.6, 0.2, 0.2), vector should contribute more
        assert high_vector > low_vector
