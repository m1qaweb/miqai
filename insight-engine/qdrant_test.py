from qdrant_client import QdrantClient, models

def test_qdrant_connection():
    """
    Tests the connection to the Qdrant service and performs a basic operation.
    """
    try:
        client = QdrantClient(host="qdrant", port=6333)
        print("Successfully created Qdrant client.")

        # Check if the collection exists, create it if it doesn't
        collection_name = "test-collection"
        collections_response = client.get_collections()
        collection_names = [c.name for c in collections_response.collections]

        if collection_name not in collection_names:
            client.recreate_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=4, distance=models.Distance.DOT),
            )
            print(f"Created collection '{collection_name}'.")
        else:
            print(f"Collection '{collection_name}' already exists.")

        # Add a test vector
        client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(id=1, vector=[0.1, 0.2, 0.3, 0.4]),
            ],
            wait=True,
        )
        print("Successfully upserted a test vector.")

        # Retrieve the test vector
        retrieved_points = client.retrieve(
            collection_name=collection_name,
            ids=[1],
        )
        print(f"Successfully retrieved point: {retrieved_points}")
        assert len(retrieved_points) == 1

        print("\nQdrant connection test successful!")
        return True

    except Exception as e:
        print(f"\nAn error occurred during the Qdrant connection test: {e}")
        return False

if __name__ == "__main__":
    test_qdrant_connection()