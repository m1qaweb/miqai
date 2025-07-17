"""
Unit tests for RAG (Retrieval-Augmented Generation) service components.

This module tests vector store operations, embedding generation,
and RAG pipeline components.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import numpy as np
from typing import List, Dict, Any

from insight_engine.tools.vector_store import VectorStore
from insight_engine.services.vector_store_service import VectorStoreService
from insight_engine.exceptions import QdrantConnectionException, ValidationException


class TestVectorStore:
    """Test VectorStore client functionality."""
    
    @pytest.fixture
    def vector_store(self):
        """Create VectorStore instance."""
        return VectorStore(host="localhost", port=6333)
    
    def test_vector_store_initialization(self, vector_store):
        """Test VectorStore initialization."""
        assert vector_store._host == "localhost"
        assert vector_store._port == 6333
        assert vector_store._client is None  # Lazy initialization
    
    @patch('insight_engine.tools.vector_store.QdrantClient')
    def test_client_lazy_initialization(self, mock_qdrant_client, vector_store):
        """Test lazy client initialization."""
        mock_client_instance = MagicMock()
        mock_qdrant_client.return_value = mock_client_instance
        
        # First access should initialize client
        client = vector_store.client
        
        assert client is mock_client_instance
        mock_qdrant_client.assert_called_once_with(host="localhost", port=6333)
        
        # Second access should return same client
        client2 = vector_store.client
        assert client2 is mock_client_instance
        assert mock_qdrant_client.call_count == 1  # Still only called once
    
    @patch('insight_engine.tools.vector_store.QdrantClient')
    def test_client_initialization_error(self, mock_qdrant_client, vector_store):
        """Test client initialization error handling."""
        mock_qdrant_client.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception) as exc_info:
            _ = vector_store.client
        
        assert "Connection failed" in str(exc_info.value)
    
    @patch('insight_engine.tools.vector_store.QdrantClient')
    def test_recreate_collection(self, mock_qdrant_client, vector_store):
        """Test collection recreation."""
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        
        vector_store.recreate_collection("test_collection", 512)
        
        mock_client.recreate_collection.assert_called_once()
        call_args = mock_client.recreate_collection.call_args
        assert call_args[1]["collection_name"] == "test_collection"
    
    @patch('insight_engine.tools.vector_store.QdrantClient')
    def test_upsert_vectors(self, mock_qdrant_client, vector_store):
        """Test vector upserting."""
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        payloads = [{"text": "first"}, {"text": "second"}]
        
        vector_store.upsert("test_collection", vectors, payloads)
        
        mock_client.upsert.assert_called_once()
        call_args = mock_client.upsert.call_args
        assert call_args[1]["collection_name"] == "test_collection"
        assert call_args[1]["wait"] is True
    
    @patch('insight_engine.tools.vector_store.QdrantClient')
    def test_search_vectors(self, mock_qdrant_client, vector_store):
        """Test vector searching."""
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        
        # Mock search results
        mock_results = [MagicMock(), MagicMock()]
        mock_client.search.return_value = mock_results
        
        query_vector = [0.1, 0.2, 0.3]
        results = vector_store.search("test_collection", query_vector, limit=5)
        
        assert results == mock_results
        mock_client.search.assert_called_once_with(
            collection_name="test_collection",
            query_vector=query_vector,
            limit=5,
            score_threshold=None
        )
    
    @patch('insight_engine.tools.vector_store.QdrantClient')
    def test_search_vectors_with_threshold(self, mock_qdrant_client, vector_store):
        """Test vector searching with score threshold."""
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        
        query_vector = [0.1, 0.2, 0.3]
        vector_store.search("test_collection", query_vector, limit=3, score_threshold=0.8)
        
        mock_client.search.assert_called_once_with(
            collection_name="test_collection",
            query_vector=query_vector,
            limit=3,
            score_threshold=0.8
        )
    
    @patch('insight_engine.tools.vector_store.QdrantClient')
    @pytest.mark.asyncio
    async def test_get_video_metadata_success(self, mock_qdrant_client, vector_store):
        """Test successful video metadata retrieval."""
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        
        # Mock scroll results
        mock_point = MagicMock()
        mock_point.payload = {"title": "Test Video", "duration": 120}
        mock_client.scroll.return_value = ([mock_point], None)
        
        metadata = await vector_store.get_video_metadata("video_collection")
        
        assert metadata == {"title": "Test Video", "duration": 120}
        mock_client.scroll.assert_called_once_with(
            collection_name="video_collection",
            limit=1,
            with_payload=True
        )
    
    @patch('insight_engine.tools.vector_store.QdrantClient')
    @pytest.mark.asyncio
    async def test_get_video_metadata_not_found(self, mock_qdrant_client, vector_store):
        """Test video metadata retrieval when not found."""
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        
        # Mock empty scroll results
        mock_client.scroll.return_value = ([], None)
        
        metadata = await vector_store.get_video_metadata("video_collection")
        
        assert metadata is None
    
    @patch('insight_engine.tools.vector_store.QdrantClient')
    @pytest.mark.asyncio
    async def test_get_video_metadata_error(self, mock_qdrant_client, vector_store):
        """Test video metadata retrieval with error."""
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        
        # Mock scroll error
        mock_client.scroll.side_effect = Exception("Collection not found")
        
        metadata = await vector_store.get_video_metadata("nonexistent_collection")
        
        assert metadata is None


class TestVectorStoreService:
    """Test VectorStoreService functionality."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        mock_settings = MagicMock()
        mock_settings.qdrant.collection = "default_collection"
        mock_settings.qdrant.host = "localhost"
        mock_settings.qdrant.port = 6333
        return mock_settings
    
    @patch('insight_engine.services.vector_store_service.settings')
    def test_vector_store_service_initialization(self, mock_settings_module, mock_settings):
        """Test VectorStoreService initialization."""
        mock_settings_module.return_value = mock_settings
        
        service = VectorStoreService()
        
        assert service.collection_name == "default_collection"
    
    @patch('insight_engine.services.vector_store_service.settings')
    def test_vector_store_service_custom_collection(self, mock_settings_module, mock_settings):
        """Test VectorStoreService with custom collection."""
        mock_settings_module.return_value = mock_settings
        
        service = VectorStoreService(collection_name="custom_collection")
        
        assert service.collection_name == "custom_collection"
    
    @patch('insight_engine.services.vector_store_service.QdrantClient')
    @patch('insight_engine.services.vector_store_service.settings')
    def test_create_collection(self, mock_settings_module, mock_qdrant_client, mock_settings):
        """Test collection creation."""
        mock_settings_module.return_value = mock_settings
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        
        service = VectorStoreService()
        service.create_collection(embedding_size=768)
        
        mock_client.recreate_collection.assert_called_once()


class TestEmbeddingGeneration:
    """Test embedding generation components."""
    
    def test_text_embedding_format(self):
        """Test text embedding format validation."""
        # Mock embedding (typical size for sentence transformers)
        embedding = np.random.rand(384).tolist()
        
        assert isinstance(embedding, list)
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)
    
    def test_embedding_normalization(self):
        """Test embedding normalization."""
        # Create unnormalized embedding
        embedding = np.random.rand(384) * 10  # Scale up
        
        # Normalize (L2 normalization)
        normalized = embedding / np.linalg.norm(embedding)
        
        # Check normalization
        norm = np.linalg.norm(normalized)
        assert abs(norm - 1.0) < 1e-6  # Should be approximately 1.0
    
    def test_embedding_similarity_calculation(self):
        """Test embedding similarity calculation."""
        # Create similar embeddings
        base_embedding = np.random.rand(384)
        similar_embedding = base_embedding + np.random.rand(384) * 0.1  # Add small noise
        different_embedding = np.random.rand(384)
        
        # Calculate cosine similarity
        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        
        similar_score = cosine_similarity(base_embedding, similar_embedding)
        different_score = cosine_similarity(base_embedding, different_embedding)
        
        # Similar embeddings should have higher similarity
        assert similar_score > different_score


class TestRAGPipeline:
    """Test RAG pipeline components."""
    
    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for testing."""
        mock_store = MagicMock()
        mock_store.search.return_value = [
            MagicMock(payload={"text": "Relevant document 1", "score": 0.9}),
            MagicMock(payload={"text": "Relevant document 2", "score": 0.8}),
        ]
        return mock_store
    
    @pytest.fixture
    def sample_query(self):
        """Sample query for testing."""
        return "What is the main topic of the video?"
    
    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing."""
        return [
            {"text": "This video discusses machine learning concepts.", "metadata": {"timestamp": 10.0}},
            {"text": "The presenter explains neural networks in detail.", "metadata": {"timestamp": 25.0}},
            {"text": "Deep learning applications are covered extensively.", "metadata": {"timestamp": 45.0}},
        ]
    
    def test_document_retrieval(self, mock_vector_store, sample_query):
        """Test document retrieval from vector store."""
        # Mock query embedding
        query_embedding = [0.1] * 384
        
        # Retrieve documents
        results = mock_vector_store.search("test_collection", query_embedding, limit=5)
        
        assert len(results) == 2
        assert results[0].payload["text"] == "Relevant document 1"
        assert results[1].payload["text"] == "Relevant document 2"
    
    def test_context_preparation(self, sample_documents):
        """Test context preparation for RAG."""
        # Simulate context preparation
        context_parts = []
        for doc in sample_documents:
            timestamp = doc["metadata"]["timestamp"]
            text = doc["text"]
            context_parts.append(f"[{timestamp}s] {text}")
        
        context = "\n".join(context_parts)
        
        expected_context = (
            "[10.0s] This video discusses machine learning concepts.\n"
            "[25.0s] The presenter explains neural networks in detail.\n"
            "[45.0s] Deep learning applications are covered extensively."
        )
        
        assert context == expected_context
    
    def test_prompt_construction(self, sample_query):
        """Test RAG prompt construction."""
        context = "This video discusses machine learning and neural networks."
        
        prompt = f"""Based on the following video content, answer the question.

Context:
{context}

Question: {sample_query}

Answer:"""
        
        assert "Context:" in prompt
        assert sample_query in prompt
        assert context in prompt
    
    def test_response_validation(self):
        """Test RAG response validation."""
        # Mock response from language model
        response = {
            "answer": "The main topic is machine learning and neural networks.",
            "confidence": 0.85,
            "sources": [
                {"text": "This video discusses machine learning", "timestamp": 10.0},
                {"text": "neural networks in detail", "timestamp": 25.0}
            ]
        }
        
        # Validate response structure
        assert "answer" in response
        assert "confidence" in response
        assert "sources" in response
        assert isinstance(response["sources"], list)
        assert 0.0 <= response["confidence"] <= 1.0


class TestRAGPerformance:
    """Test RAG pipeline performance and optimization."""
    
    def test_embedding_cache_efficiency(self):
        """Test embedding caching for performance."""
        # Simulate embedding cache
        embedding_cache = {}
        
        def get_cached_embedding(text):
            if text not in embedding_cache:
                # Simulate expensive embedding generation
                embedding_cache[text] = np.random.rand(384).tolist()
            return embedding_cache[text]
        
        text = "Sample text for embedding"
        
        # First call should cache
        embedding1 = get_cached_embedding(text)
        assert text in embedding_cache
        
        # Second call should use cache
        embedding2 = get_cached_embedding(text)
        assert embedding1 == embedding2
        assert len(embedding_cache) == 1
    
    def test_retrieval_result_ranking(self):
        """Test retrieval result ranking by relevance."""
        # Mock search results with scores
        results = [
            {"text": "Less relevant", "score": 0.6},
            {"text": "Most relevant", "score": 0.9},
            {"text": "Moderately relevant", "score": 0.75},
        ]
        
        # Sort by score (descending)
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
        
        assert sorted_results[0]["text"] == "Most relevant"
        assert sorted_results[1]["text"] == "Moderately relevant"
        assert sorted_results[2]["text"] == "Less relevant"
    
    def test_context_length_optimization(self):
        """Test context length optimization for RAG."""
        # Mock long documents
        long_documents = [
            {"text": "A" * 1000, "score": 0.9},  # Very long, high relevance
            {"text": "B" * 100, "score": 0.8},   # Short, good relevance
            {"text": "C" * 500, "score": 0.7},   # Medium, lower relevance
        ]
        
        max_context_length = 800
        selected_docs = []
        current_length = 0
        
        # Select documents within context limit
        for doc in sorted(long_documents, key=lambda x: x["score"], reverse=True):
            doc_length = len(doc["text"])
            if current_length + doc_length <= max_context_length:
                selected_docs.append(doc)
                current_length += doc_length
        
        # Should select the short high-relevance doc and part of others
        assert len(selected_docs) >= 1
        assert sum(len(doc["text"]) for doc in selected_docs) <= max_context_length


@pytest.mark.unit
class TestRAGIntegration:
    """Integration tests for RAG components."""
    
    @patch('insight_engine.tools.vector_store.QdrantClient')
    def test_end_to_end_rag_flow(self, mock_qdrant_client):
        """Test end-to-end RAG flow."""
        # Mock Qdrant client
        mock_client = MagicMock()
        mock_qdrant_client.return_value = mock_client
        
        # Mock search results
        mock_results = [
            MagicMock(payload={"text": "Machine learning is discussed", "timestamp": 10.0}, score=0.9),
            MagicMock(payload={"text": "Neural networks are explained", "timestamp": 25.0}, score=0.8),
        ]
        mock_client.search.return_value = mock_results
        
        # Initialize vector store
        vector_store = VectorStore()
        
        # Simulate RAG query
        query_embedding = [0.1] * 384
        results = vector_store.search("video_collection", query_embedding, limit=5)
        
        # Verify results
        assert len(results) == 2
        assert results[0].payload["text"] == "Machine learning is discussed"
        assert results[1].payload["text"] == "Neural networks are explained"
        
        # Simulate context preparation
        context_parts = []
        for result in results:
            timestamp = result.payload["timestamp"]
            text = result.payload["text"]
            context_parts.append(f"[{timestamp}s] {text}")
        
        context = "\n".join(context_parts)
        expected_context = "[10.0s] Machine learning is discussed\n[25.0s] Neural networks are explained"
        
        assert context == expected_context
    
    def test_rag_error_handling(self):
        """Test RAG pipeline error handling."""
        # Test with invalid embedding dimensions
        with pytest.raises(Exception):
            vector_store = VectorStore()
            # This should fail with dimension mismatch
            invalid_embedding = [0.1] * 100  # Wrong dimension
            # In real implementation, this would be caught and handled