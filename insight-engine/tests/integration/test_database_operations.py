"""
Integration tests for database operations.

This module tests Redis and Qdrant database interactions,
connection handling, and data persistence.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
import redis.asyncio as redis
from qdrant_client import QdrantClient, models
import numpy as np

from insight_engine.services.redis_service import RedisService, get_redis_service
from insight_engine.tools.vector_store import VectorStore
from insight_engine.services.vector_store_service import VectorStoreService
from tests.utils import requires_redis, requires_qdrant, DatabaseTestHelper


class TestRedisIntegration:
    """Test Redis database integration."""
    
    @pytest.mark.integration
    @requires_redis
    async def test_redis_connection(self, test_redis_client):
        """Test Redis connection and basic operations."""
        # Test connection
        await test_redis_client.ping()
        
        # Test basic operations
        await test_redis_client.set("test_key", "test_value")
        value = await test_redis_client.get("test_key")
        assert value == "test_value"
        
        # Cleanup
        await test_redis_client.delete("test_key")
    
    @pytest.mark.integration
    @requires_redis
    async def test_redis_service_integration(self):
        """Test RedisService integration."""
        redis_service = RedisService()
        
        # Test set and get
        await redis_service.set("integration_test", "test_data", ttl=60)
        result = await redis_service.get("integration_test")
        assert result == "test_data"
        
        # Test TTL expiration (quick test)
        await redis_service.set("ttl_test", "data", ttl=1)
        await asyncio.sleep(2)
        expired_result = await redis_service.get("ttl_test")
        assert expired_result is None
    
    @pytest.mark.integration
    @requires_redis
    async def test_redis_service_error_handling(self):
        """Test Redis service error handling."""
        # Test with invalid Redis configuration
        with patch('redis.asyncio.Redis') as mock_redis:
            mock_redis.return_value.get.side_effect = redis.ConnectionError("Connection failed")
            
            redis_service = RedisService()
            result = await redis_service.get("test_key")
            assert result is None  # Should handle error gracefully
    
    @pytest.mark.integration
    @requires_redis
    async def test_redis_concurrent_operations(self, test_redis_client):
        """Test concurrent Redis operations."""
        async def set_value(key, value):
            await test_redis_client.set(key, value)
            return await test_redis_client.get(key)
        
        # Run concurrent operations
        tasks = [
            set_value(f"concurrent_key_{i}", f"value_{i}")
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all operations succeeded
        for i, result in enumerate(results):
            assert result == f"value_{i}"
        
        # Cleanup
        keys_to_delete = [f"concurrent_key_{i}" for i in range(10)]
        await test_redis_client.delete(*keys_to_delete)
    
    @pytest.mark.integration
    @requires_redis
    async def test_redis_data_types(self, test_redis_client):
        """Test Redis with different data types."""
        # String
        await test_redis_client.set("string_key", "string_value")
        assert await test_redis_client.get("string_key") == "string_value"
        
        # Hash
        await test_redis_client.hset("hash_key", "field1", "value1")
        await test_redis_client.hset("hash_key", "field2", "value2")
        hash_data = await test_redis_client.hgetall("hash_key")
        assert hash_data == {"field1": "value1", "field2": "value2"}
        
        # List
        await test_redis_client.lpush("list_key", "item1", "item2", "item3")
        list_data = await test_redis_client.lrange("list_key", 0, -1)
        assert "item1" in list_data
        
        # Cleanup
        await test_redis_client.delete("string_key", "hash_key", "list_key")


class TestQdrantIntegration:
    """Test Qdrant vector database integration."""
    
    @pytest.mark.integration
    @requires_qdrant
    def test_qdrant_connection(self, test_qdrant_client):
        """Test Qdrant connection and basic operations."""
        # Test connection by getting collections
        collections = test_qdrant_client.get_collections()
        assert hasattr(collections, 'collections')
    
    @pytest.mark.integration
    @requires_qdrant
    def test_qdrant_collection_operations(self, test_qdrant_client):
        """Test Qdrant collection creation and management."""
        collection_name = "test_integration_collection"
        
        try:
            # Create collection
            test_qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=128,
                    distance=models.Distance.COSINE
                )
            )
            
            # Verify collection exists
            collections = test_qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            assert collection_name in collection_names
            
            # Get collection info
            collection_info = test_qdrant_client.get_collection(collection_name)
            assert collection_info.config.params.vectors.size == 128
            
        finally:
            # Cleanup
            try:
                test_qdrant_client.delete_collection(collection_name)
            except Exception:
                pass  # Ignore cleanup errors
    
    @pytest.mark.integration
    @requires_qdrant
    def test_qdrant_vector_operations(self, test_qdrant_client):
        """Test Qdrant vector insertion and search."""
        collection_name = "test_vector_operations"
        
        try:
            # Create collection
            test_qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=4,  # Small size for testing
                    distance=models.Distance.COSINE
                )
            )
            
            # Insert vectors
            vectors = [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
            ]
            payloads = [
                {"text": "first vector", "category": "A"},
                {"text": "second vector", "category": "B"},
                {"text": "third vector", "category": "A"},
            ]
            
            test_qdrant_client.upsert(
                collection_name=collection_name,
                points=models.Batch(
                    ids=[1, 2, 3],
                    vectors=vectors,
                    payloads=payloads
                )
            )
            
            # Search for similar vectors
            search_results = test_qdrant_client.search(
                collection_name=collection_name,
                query_vector=[1.0, 0.1, 0.0, 0.0],  # Similar to first vector
                limit=2
            )
            
            assert len(search_results) == 2
            assert search_results[0].id == 1  # Should be most similar
            assert search_results[0].payload["text"] == "first vector"
            
        finally:
            # Cleanup
            try:
                test_qdrant_client.delete_collection(collection_name)
            except Exception:
                pass
    
    @pytest.mark.integration
    @requires_qdrant
    def test_vector_store_integration(self):
        """Test VectorStore class integration with Qdrant."""
        vector_store = VectorStore(host="localhost", port=6333)
        collection_name = "test_vector_store_integration"
        
        try:
            # Create collection
            vector_store.recreate_collection(collection_name, 4)
            
            # Insert vectors
            vectors = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
            payloads = [{"text": "vector 1"}, {"text": "vector 2"}]
            
            vector_store.upsert(collection_name, vectors, payloads)
            
            # Search
            results = vector_store.search(
                collection_name,
                [1.0, 0.1, 0.0, 0.0],
                limit=1
            )
            
            assert len(results) == 1
            assert results[0].payload["text"] == "vector 1"
            
        finally:
            # Cleanup
            try:
                vector_store.client.delete_collection(collection_name)
            except Exception:
                pass
    
    @pytest.mark.integration
    @requires_qdrant
    async def test_vector_store_service_integration(self):
        """Test VectorStoreService integration."""
        service = VectorStoreService(collection_name="test_service_collection")
        
        try:
            # Create collection
            service.create_collection(embedding_size=4)
            
            # The service should work with the created collection
            # This test verifies the service can interact with Qdrant
            assert service.collection_name == "test_service_collection"
            
        finally:
            # Cleanup
            try:
                service.client.delete_collection("test_service_collection")
            except Exception:
                pass


class TestDatabaseErrorHandling:
    """Test database error handling and resilience."""
    
    @pytest.mark.integration
    async def test_redis_connection_failure_handling(self):
        """Test Redis connection failure handling."""
        # Test with invalid Redis URL
        with patch('redis.asyncio.Redis.from_url') as mock_redis:
            mock_redis.side_effect = redis.ConnectionError("Connection refused")
            
            redis_service = RedisService()
            
            # Should handle connection errors gracefully
            result = await redis_service.get("test_key")
            assert result is None
    
    @pytest.mark.integration
    def test_qdrant_connection_failure_handling(self):
        """Test Qdrant connection failure handling."""
        # Test with invalid Qdrant configuration
        vector_store = VectorStore(host="invalid-host", port=9999)
        
        # Should raise an exception when trying to connect
        with pytest.raises(Exception):
            _ = vector_store.client
    
    @pytest.mark.integration
    @requires_redis
    async def test_redis_operation_timeout(self, test_redis_client):
        """Test Redis operation timeout handling."""
        # Set a very short timeout
        test_redis_client.socket_timeout = 0.001
        
        try:
            # This might timeout or succeed depending on system speed
            await test_redis_client.set("timeout_test", "value")
        except (redis.TimeoutError, redis.ConnectionError):
            # Expected behavior for timeout
            pass
    
    @pytest.mark.integration
    @requires_qdrant
    def test_qdrant_invalid_collection_operations(self, test_qdrant_client):
        """Test Qdrant operations on non-existent collections."""
        # Try to search in non-existent collection
        with pytest.raises(Exception):
            test_qdrant_client.search(
                collection_name="nonexistent_collection",
                query_vector=[1.0, 0.0, 0.0, 0.0],
                limit=1
            )


class TestDatabasePerformance:
    """Test database performance characteristics."""
    
    @pytest.mark.integration
    @requires_redis
    async def test_redis_bulk_operations_performance(self, test_redis_client):
        """Test Redis bulk operations performance."""
        import time
        
        # Test bulk set operations
        start_time = time.time()
        
        pipe = test_redis_client.pipeline()
        for i in range(100):
            pipe.set(f"bulk_key_{i}", f"value_{i}")
        await pipe.execute()
        
        bulk_time = time.time() - start_time
        
        # Test individual operations
        start_time = time.time()
        for i in range(100, 200):
            await test_redis_client.set(f"individual_key_{i}", f"value_{i}")
        individual_time = time.time() - start_time
        
        # Bulk operations should be faster
        assert bulk_time < individual_time
        
        # Cleanup
        keys_to_delete = [f"bulk_key_{i}" for i in range(100)]
        keys_to_delete.extend([f"individual_key_{i}" for i in range(100, 200)])
        await test_redis_client.delete(*keys_to_delete)
    
    @pytest.mark.integration
    @requires_qdrant
    def test_qdrant_batch_operations_performance(self, test_qdrant_client):
        """Test Qdrant batch operations performance."""
        collection_name = "test_performance_collection"
        
        try:
            # Create collection
            test_qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=128,
                    distance=models.Distance.COSINE
                )
            )
            
            # Generate test vectors
            vectors = [np.random.rand(128).tolist() for _ in range(100)]
            payloads = [{"id": i, "text": f"document {i}"} for i in range(100)]
            
            import time
            start_time = time.time()
            
            # Batch upsert
            test_qdrant_client.upsert(
                collection_name=collection_name,
                points=models.Batch(
                    ids=list(range(100)),
                    vectors=vectors,
                    payloads=payloads
                )
            )
            
            batch_time = time.time() - start_time
            
            # Should complete within reasonable time
            assert batch_time < 10.0  # 10 seconds max
            
            # Test search performance
            start_time = time.time()
            results = test_qdrant_client.search(
                collection_name=collection_name,
                query_vector=np.random.rand(128).tolist(),
                limit=10
            )
            search_time = time.time() - start_time
            
            assert len(results) == 10
            assert search_time < 1.0  # 1 second max
            
        finally:
            # Cleanup
            try:
                test_qdrant_client.delete_collection(collection_name)
            except Exception:
                pass


@pytest.mark.integration
class TestDatabaseIntegration:
    """Test integration between different database systems."""
    
    @requires_redis
    @requires_qdrant
    async def test_redis_qdrant_integration(self, test_redis_client, test_qdrant_client):
        """Test integration between Redis and Qdrant."""
        collection_name = "test_integration_collection"
        
        try:
            # Store metadata in Redis
            video_metadata = {
                "id": "video-123",
                "title": "Test Video",
                "duration": 120.0,
                "status": "processed"
            }
            
            await test_redis_client.hset(
                "video:video-123",
                mapping=video_metadata
            )
            
            # Store vectors in Qdrant
            test_qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=4,
                    distance=models.Distance.COSINE
                )
            )
            
            test_qdrant_client.upsert(
                collection_name=collection_name,
                points=models.Batch(
                    ids=["video-123"],
                    vectors=[[1.0, 0.0, 0.0, 0.0]],
                    payloads=[{"video_id": "video-123", "segment": "intro"}]
                )
            )
            
            # Retrieve and verify integration
            redis_data = await test_redis_client.hgetall("video:video-123")
            assert redis_data["id"] == "video-123"
            
            qdrant_results = test_qdrant_client.search(
                collection_name=collection_name,
                query_vector=[1.0, 0.1, 0.0, 0.0],
                limit=1
            )
            
            assert len(qdrant_results) == 1
            assert qdrant_results[0].payload["video_id"] == "video-123"
            
        finally:
            # Cleanup
            await test_redis_client.delete("video:video-123")
            try:
                test_qdrant_client.delete_collection(collection_name)
            except Exception:
                pass
    
    @requires_redis
    async def test_database_helper_utilities(self, test_redis_client):
        """Test database helper utilities."""
        helper = DatabaseTestHelper(redis_client=test_redis_client)
        
        # Set up test data
        await test_redis_client.set("test_key_1", "value1")
        await test_redis_client.set("test_key_2", "value2")
        await test_redis_client.set("other_key", "other_value")
        
        # Test cleanup utility
        await helper.clear_redis_keys("test_*")
        
        # Verify cleanup
        assert await test_redis_client.get("test_key_1") is None
        assert await test_redis_client.get("test_key_2") is None
        assert await test_redis_client.get("other_key") == "other_value"
        
        # Cleanup remaining
        await test_redis_client.delete("other_key")