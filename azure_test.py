import os
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential

def test_azure_openai_embedding():
    """
    Tests the connection and authentication to the Azure OpenAI embedding endpoint.
    """
    try:
        endpoint = "https://miqaela.openai.azure.com/"
        api_key = "EEfEA5OXRNgMNG0Y4Ct9nfD6XHTaWCT06Te8Pz99yaJ3FfbucODzJQQJ99BGACF24PCXJ3w3AAABACOGhSbe"
        deployment = "text-embedding-3-large"
        api_version = "2024-02-01"

        client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key,
        )

        response = client.embeddings.create(
            input=["test phrase 1", "test phrase 2"],
            model=deployment
        )

        print("Successfully received embeddings.")
        print(f"Usage: {response.usage}")
        for item in response.data:
            print(f"Embedding for index {item.index} has length: {len(item.embedding)}")
        return True

    except Exception as e:
        print(f"An error occurred: {e}")
        return False

if __name__ == "__main__":
    test_azure_openai_embedding()