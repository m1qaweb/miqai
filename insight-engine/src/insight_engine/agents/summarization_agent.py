from langchain_google_genai import ChatGoogleGenerativeAI
from typing import AsyncGenerator
from langchain.schema.runnable import Runnable
from insight_engine.tools.vector_store import VectorStore
from .rag_utils import create_rag_chain, RAGInput
from langchain_community.vectorstores import Qdrant
from langchain_community.embeddings import OpenAIEmbeddings


class SummarizationAgent:
    """
    An agent that uses a Retrieval-Augmented Generation (RAG) chain
    to produce context-grounded summaries.
    """

    def __init__(self, vector_store: VectorStore, collection_name: str):
        """
        Initializes the SummarizationAgent.

        Args:
            vector_store: An instance of the VectorStore service.
            collection_name: The name of the collection to use.
        """
        self.vector_store = vector_store
        
        # 1. Create a retriever from the VectorStore instance
        qdrant = Qdrant(
            client=self.vector_store.client,
            collection_name=collection_name,
            embeddings=OpenAIEmbeddings(),
        )
        retriever = qdrant.as_retriever()

        # 2. Instantiate the language model
        model = ChatGoogleGenerativeAI(model="gemini-pro")

        # 3. Construct the RAG chain using the shared utility
        self.rag_chain: Runnable = create_rag_chain(model, retriever)
        self.retriever = retriever

    async def generate_summary(self, rag_input: RAGInput) -> AsyncGenerator[str, None]:
        """
        Invokes the RAG chain with the user's question to generate a summary.

        Args:
            rag_input: An object containing the user's query and chat history.

        Returns:
            The content of the AI's response as a string.
        """
        retrieved_docs = await self.retriever.ainvoke(rag_input.query)
        async for chunk in self.rag_chain.astream({
            "context": retrieved_docs,
            "question": rag_input.query
        }):
            yield chunk
