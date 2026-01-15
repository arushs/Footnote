"""Tests for the embedding service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.embedding import (
    embed_text,
    embed_batch,
    rerank,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
)


class TestEmbedText:
    """Tests for single text embedding."""

    @pytest.mark.asyncio
    async def test_embed_returns_768_dimensions(self):
        """Embedding should return 768-dimensional vector."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * EMBEDDING_DIM}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await embed_text("test query")

            assert len(result) == EMBEDDING_DIM
            assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_embed_text_calls_api_correctly(self):
        """Embedding should call the API with correct parameters."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * EMBEDDING_DIM}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            await embed_text("test query")

            # Verify API was called
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            assert "json" in call_kwargs.kwargs
            assert call_kwargs.kwargs["json"]["input"] == "test query"
            assert call_kwargs.kwargs["json"]["model"] == EMBEDDING_MODEL

    @pytest.mark.asyncio
    async def test_embed_text_handles_empty_string(self):
        """Embedding should handle empty string input."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.0] * EMBEDDING_DIM}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await embed_text("")

            assert len(result) == EMBEDDING_DIM


class TestEmbedBatch:
    """Tests for batch embedding."""

    @pytest.mark.asyncio
    async def test_batch_embedding_multiple_texts(self):
        """Batch embedding should handle multiple texts."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * EMBEDDING_DIM},
                {"embedding": [0.2] * EMBEDDING_DIM},
                {"embedding": [0.3] * EMBEDDING_DIM},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            texts = ["text one", "text two", "text three"]
            results = await embed_batch(texts)

            assert len(results) == 3
            for result in results:
                assert len(result) == EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_batch_embedding_single_text(self):
        """Batch embedding should work with single text."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * EMBEDDING_DIM}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            texts = ["single text"]
            results = await embed_batch(texts)

            assert len(results) == 1
            assert len(results[0]) == EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_batch_embedding_preserves_order(self):
        """Batch embedding should preserve input order."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * EMBEDDING_DIM},  # First text
                {"embedding": [0.5] * EMBEDDING_DIM},  # Second text
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            texts = ["first", "second"]
            results = await embed_batch(texts)

            assert results[0][0] == 0.1  # First embedding
            assert results[1][0] == 0.5  # Second embedding


class TestRerank:
    """Tests for reranking functionality."""

    @pytest.mark.asyncio
    async def test_rerank_returns_indices_and_scores(self):
        """Rerank should return list of (index, score) tuples."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"index": 2, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.80},
                {"index": 1, "relevance_score": 0.65},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            query = "What is the revenue?"
            documents = ["Revenue was $10M", "Costs increased", "Revenue grew 20%"]
            results = await rerank(query, documents, top_k=3)

            assert len(results) == 3
            # Results should be tuples of (index, score)
            assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
            # First result should have highest score
            assert results[0] == (2, 0.95)

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(self):
        """Rerank should respect top_k parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
                {"index": 1, "relevance_score": 0.8},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await rerank("query", ["doc1", "doc2", "doc3"], top_k=2)

            # Verify top_k was passed to API
            call_kwargs = mock_client.post.call_args.kwargs
            assert call_kwargs["json"]["top_n"] == 2

    @pytest.mark.asyncio
    async def test_rerank_calls_correct_endpoint(self):
        """Rerank should call the rerank API endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            await rerank("query", ["doc1"], top_k=1)

            # Verify correct endpoint was called
            call_args = mock_client.post.call_args
            assert "rerank" in call_args.args[0]


class TestEmbeddingDimension:
    """Tests for embedding dimension constant."""

    def test_embedding_dim_is_768(self):
        """Embedding dimension should be 768 for the model."""
        assert EMBEDDING_DIM == 768

    def test_embedding_model_defined(self):
        """Embedding model should be defined."""
        assert EMBEDDING_MODEL is not None
        assert len(EMBEDDING_MODEL) > 0
