"""Tests for the embedding service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.embedding import (
    embed_text,
    embed_batch,
    rerank,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    RERANK_MODEL,
)


def create_mock_embedding_response(embeddings: list[list[float]]):
    """Create a mock embedding response object."""
    response = MagicMock()
    response.data = [
        MagicMock(embedding=emb) for emb in embeddings
    ]
    return response


def create_mock_rerank_response(results: list[tuple[int, float]]):
    """Create a mock rerank response object."""
    response = MagicMock()
    response.results = [
        MagicMock(index=idx, relevance_score=score) for idx, score in results
    ]
    return response


class TestEmbedText:
    """Tests for single text embedding."""

    @pytest.mark.asyncio
    async def test_embed_returns_768_dimensions(self):
        """Embedding should return 768-dimensional vector."""
        mock_response = create_mock_embedding_response([[0.1] * EMBEDDING_DIM])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await embed_text("test query")

            assert len(result) == EMBEDDING_DIM
            assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_embed_text_calls_api_correctly(self):
        """Embedding should call the API with correct parameters."""
        mock_response = create_mock_embedding_response([[0.1] * EMBEDDING_DIM])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

            await embed_text("test query")

            mock_client.embeddings.create.assert_called_once_with(
                model=EMBEDDING_MODEL,
                input="test query",
            )

    @pytest.mark.asyncio
    async def test_embed_text_handles_empty_string(self):
        """Embedding should handle empty string input."""
        mock_response = create_mock_embedding_response([[0.0] * EMBEDDING_DIM])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await embed_text("")

            assert len(result) == EMBEDDING_DIM


class TestEmbedBatch:
    """Tests for batch embedding."""

    @pytest.mark.asyncio
    async def test_batch_embedding_multiple_texts(self):
        """Batch embedding should handle multiple texts."""
        mock_response = create_mock_embedding_response([
            [0.1] * EMBEDDING_DIM,
            [0.2] * EMBEDDING_DIM,
            [0.3] * EMBEDDING_DIM,
        ])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

            texts = ["text one", "text two", "text three"]
            results = await embed_batch(texts)

            assert len(results) == 3
            for result in results:
                assert len(result) == EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_batch_embedding_single_text(self):
        """Batch embedding should work with single text."""
        mock_response = create_mock_embedding_response([[0.1] * EMBEDDING_DIM])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

            texts = ["single text"]
            results = await embed_batch(texts)

            assert len(results) == 1
            assert len(results[0]) == EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_batch_embedding_preserves_order(self):
        """Batch embedding should preserve input order."""
        mock_response = create_mock_embedding_response([
            [0.1] * EMBEDDING_DIM,
            [0.5] * EMBEDDING_DIM,
        ])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

            texts = ["first", "second"]
            results = await embed_batch(texts)

            assert results[0][0] == 0.1
            assert results[1][0] == 0.5


class TestRerank:
    """Tests for reranking functionality."""

    @pytest.mark.asyncio
    async def test_rerank_returns_indices_and_scores(self):
        """Rerank should return list of (index, score) tuples."""
        mock_response = create_mock_rerank_response([
            (2, 0.95),
            (0, 0.80),
            (1, 0.65),
        ])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.rerank.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

            query = "What is the revenue?"
            documents = ["Revenue was $10M", "Costs increased", "Revenue grew 20%"]
            results = await rerank(query, documents, top_k=3)

            assert len(results) == 3
            assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
            assert results[0] == (2, 0.95)

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(self):
        """Rerank should respect top_k parameter."""
        mock_response = create_mock_rerank_response([
            (0, 0.9),
            (1, 0.8),
        ])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.rerank.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

            await rerank("query", ["doc1", "doc2", "doc3"], top_k=2)

            mock_client.rerank.create.assert_called_once_with(
                model=RERANK_MODEL,
                query="query",
                documents=["doc1", "doc2", "doc3"],
                top_n=2,
            )

    @pytest.mark.asyncio
    async def test_rerank_uses_correct_model(self):
        """Rerank should use the correct rerank model."""
        mock_response = create_mock_rerank_response([])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.rerank.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_client.return_value.__aexit__ = AsyncMock(return_value=None)

            await rerank("query", ["doc1"], top_k=1)

            call_kwargs = mock_client.rerank.create.call_args.kwargs
            assert call_kwargs["model"] == RERANK_MODEL


class TestEmbeddingDimension:
    """Tests for embedding dimension constant."""

    def test_embedding_dim_is_768(self):
        """Embedding dimension should be 768 for the model."""
        assert EMBEDDING_DIM == 768

    def test_embedding_model_defined(self):
        """Embedding model should be defined."""
        assert EMBEDDING_MODEL is not None
        assert len(EMBEDDING_MODEL) > 0

    def test_rerank_model_defined(self):
        """Rerank model should be defined."""
        assert RERANK_MODEL is not None
        assert len(RERANK_MODEL) > 0
