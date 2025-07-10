"""
RAG-based question-answering chain for video insights.
"""

from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from insight_engine.services.vector_store_service import (
    VectorStoreService,
)
from typing import AsyncGenerator, Dict, Any


class RAGChain:
    """
    A chain that orchestrates Retrieval-Augmented Generation for answering
    questions, with support for streaming and multi-modal context.
    """

    def __init__(self, vector_store: VectorStoreService, collection_name: str):
        """
        Initializes the RAG chain components.

        Args:
            vector_store: An initialized instance of VectorStoreService.
            collection_name: The name of the collection to query.
        """
        self.vector_store = vector_store
        self.collection_name = collection_name
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-pro", temperature=0.2, stream=True
        )

        self.prompt_template = """
        You are a helpful AI assistant. Answer the user's question based *only* 
        on the following context. The context contains both a text transcript 
        and a list of objects detected in the video at that time. Use both
        to form a comprehensive answer. If the context does not contain the answer,
        state that you cannot answer the question with the provided information.

        CONTEXT:
        {context}

        QUESTION:
        {question}

        ANSWER:
        """
        self.prompt = PromptTemplate(
            template=self.prompt_template, input_variables=["context", "question"]
        )
        self.chain = self.prompt | self.llm

    def _format_context(self, search_results: list[Dict[str, Any]]) -> str:
        """Formats the search results into a single context string."""
        context_parts = []
        for hit in search_results:
            text = hit.get("payload", {}).get("chunk_text", "")
            visual_context = hit.get("payload", {}).get("visual_context")
            
            part = f"Transcript chunk: \"{text}\""
            if visual_context:
                part += f"\nDetected objects: {', '.join(visual_context)}"
            
            context_parts.append(part)
        
        return "\n---\n".join(context_parts)

    def _get_context(self, question: str) -> str:
        """Embeds a query and retrieves formatted context from the vector store."""
        query_vector = self.embeddings.embed_query(question)
        search_results = self.vector_store.search(
            collection_name=self.collection_name, query_vector=query_vector, limit=5
        )
        return self._format_context(search_results)

    async def stream(self, question: str) -> AsyncGenerator[str, None]:
        """
        Executes the RAG chain and streams the response.
        """
        context = self._get_context(question)
        if not context:
            yield "I could not find any relevant information to answer your question."
            return

        async for chunk in self.chain.astream(
            {"context": context, "question": question}
        ):
            yield chunk.content

    def run(self, question: str) -> str:
        """
        Executes the RAG chain for a non-streaming response.
        """
        context = self._get_context(question)
        if not context:
            return "I could not find any relevant information to answer your question."

        response = self.chain.invoke({"context": context, "question": question})
        return response.content
