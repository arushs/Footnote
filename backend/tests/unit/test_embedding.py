"""Tests for the embedding service using Fireworks AI."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.embedding import (
    embed_document,
    embed_query,
    embed_documents_batch,
    rerank,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    RERANK_MODEL,
)


def create_mock_embedding_response(embeddings: list[list[float]]):
    """Create a mock embedding response object."""
    response = MagicMock()
    response.data = [MagicMock(embedding=emb) for emb in embeddings]
    return response


class TestEmbedDocument:
    """Tests for document embedding."""

    @pytest.mark.asyncio
    async def test_embed_document_returns_768_dimensions(self):
        """Embedding should return 768-dimensional vector."""
        mock_response = create_mock_embedding_response([[0.1] * EMBEDDING_DIM])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await embed_document("test document")

            assert len(result) == EMBEDDING_DIM
            assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_embed_document_adds_prefix(self):
        """Document embedding should add search_document prefix."""
        mock_response = create_mock_embedding_response([[0.1] * EMBEDDING_DIM])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            await embed_document("test document")

            mock_client.embeddings.create.assert_called_once_with(
                model=EMBEDDING_MODEL,
                input="search_document: test document",
            )

    @pytest.mark.asyncio
    async def test_embed_document_raises_on_empty_text(self):
        """Document embedding should raise ValueError for empty text."""
        with pytest.raises(ValueError, match="Cannot embed empty text"):
            await embed_document("")

    @pytest.mark.asyncio
    async def test_embed_document_raises_on_whitespace(self):
        """Document embedding should raise ValueError for whitespace-only text."""
        with pytest.raises(ValueError, match="Cannot embed empty text"):
            await embed_document("   ")


class TestEmbedQuery:
    """Tests for query embedding."""

    @pytest.mark.asyncio
    async def test_embed_query_returns_768_dimensions(self):
        """Query embedding should return 768-dimensional vector."""
        mock_response = create_mock_embedding_response([[0.1] * EMBEDDING_DIM])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await embed_query("test query")

            assert len(result) == EMBEDDING_DIM
            assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_embed_query_adds_prefix(self):
        """Query embedding should add search_query prefix."""
        mock_response = create_mock_embedding_response([[0.1] * EMBEDDING_DIM])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            await embed_query("test query")

            mock_client.embeddings.create.assert_called_once_with(
                model=EMBEDDING_MODEL,
                input="search_query: test query",
            )

    @pytest.mark.asyncio
    async def test_embed_query_raises_on_empty_query(self):
        """Query embedding should raise ValueError for empty query."""
        with pytest.raises(ValueError, match="Cannot embed empty query"):
            await embed_query("")


class TestEmbedDocumentsBatch:
    """Tests for batch document embedding."""

    @pytest.mark.asyncio
    async def test_batch_embedding_multiple_texts(self):
        """Batch embedding should handle multiple texts."""
        mock_response = create_mock_embedding_response([
            [0.1] * EMBEDDING_DIM,
            [0.2] * EMBEDDING_DIM,
            [0.3] * EMBEDDING_DIM,
        ])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            texts = ["text one", "text two", "text three"]
            results = await embed_documents_batch(texts)

            assert len(results) == 3
            for result in results:
                assert len(result) == EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_batch_embedding_adds_prefix_to_all(self):
        """Batch embedding should add search_document prefix to all texts."""
        mock_response = create_mock_embedding_response([
            [0.1] * EMBEDDING_DIM,
            [0.2] * EMBEDDING_DIM,
        ])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            texts = ["first", "second"]
            await embed_documents_batch(texts)

            mock_client.embeddings.create.assert_called_once_with(
                model=EMBEDDING_MODEL,
                input=["search_document: first", "search_document: second"],
            )

    @pytest.mark.asyncio
    async def test_batch_embedding_empty_list(self):
        """Batch embedding should return empty list for empty input."""
        results = await embed_documents_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_embedding_preserves_order(self):
        """Batch embedding should preserve input order."""
        mock_response = create_mock_embedding_response([
            [0.1] * EMBEDDING_DIM,
            [0.5] * EMBEDDING_DIM,
        ])

        with patch("app.services.embedding._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            texts = ["first", "second"]
            results = await embed_documents_batch(texts)

            assert results[0][0] == 0.1
            assert results[1][0] == 0.5


class TestRerank:
    """Tests for reranking functionality."""

    @pytest.mark.asyncio
    async def test_rerank_returns_indices_and_scores(self):
        """Rerank should return list of (index, score) tuples."""
        mock_response_data = {
            "results": [
                {"index": 2, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.80},
                {"index": 1, "relevance_score": 0.65},
            ]
        }

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_http_client = MagicMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_http_client

            query = "What is the revenue?"
            documents = ["Revenue was $10M", "Costs increased", "Revenue grew 20%"]
            results = await rerank(query, documents, top_k=3)

            assert len(results) == 3
            assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
            assert results[0] == (2, 0.95)

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(self):
        """Rerank should respect top_k parameter."""
        mock_response_data = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
                {"index": 1, "relevance_score": 0.8},
            ]
        }

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_http_client = MagicMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_http_client

            await rerank("query", ["doc1", "doc2", "doc3"], top_k=2)

            # Verify the JSON payload
            call_args = mock_http_client.post.call_args
            json_payload = call_args.kwargs["json"]
            assert json_payload["top_n"] == 2

    @pytest.mark.asyncio
    async def test_rerank_uses_correct_model(self):
        """Rerank should use the correct rerank model."""
        mock_response_data = {"results": []}

        with patch("httpx.AsyncClient") as MockAsyncClient:
            mock_http_client = MagicMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            MockAsyncClient.return_value = mock_http_client

            await rerank("query", ["doc1"], top_k=1)

            call_args = mock_http_client.post.call_args
            json_payload = call_args.kwargs["json"]
            assert json_payload["model"] == RERANK_MODEL

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self):
        """Rerank should return empty list for empty documents."""
        results = await rerank("query", [], top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_rerank_raises_on_empty_query(self):
        """Rerank should raise ValueError for empty query."""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await rerank("", ["doc1", "doc2"])


class TestEmbeddingConstants:
    """Tests for embedding constants."""

    def test_embedding_dim_is_768(self):
        """Embedding dimension should be 768 for the model."""
        assert EMBEDDING_DIM == 768

    def test_embedding_model_is_nomic(self):
        """Embedding model should be nomic-embed-text."""
        assert "nomic" in EMBEDDING_MODEL.lower()

    def test_rerank_model_is_qwen(self):
        """Rerank model should be qwen3-reranker."""
        assert "qwen" in RERANK_MODEL.lower()
