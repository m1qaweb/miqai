import asyncio
import json
import logging
import os
from typing import AsyncGenerator, Dict, List, Any

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.vectorstores import VectorStoreRetriever
from pydantic import BaseModel, Field
from .rag_utils import RAGInput, create_rag_chain

# --- 1. Structured Logging Setup ---
# Configure a logger that outputs JSON for better observability.
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_object: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }
        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_object)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("rag_agent")
logger.addHandler(handler)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))


# --- 2. Pydantic Models for Input/Output ---
class RAGOutput(BaseModel):
    """Output schema for the RAG agent stream."""
    content: str
    context: List[Dict[str, Any]]

async def run_rag_agent(
    agent_input: RAGInput, llm: BaseChatModel, retriever: VectorStoreRetriever
) -> AsyncGenerator[str, None]:
    """
    Asynchronously runs the RAG agent and streams the response.

    Args:
        agent_input: The user's query and chat history.
        llm: An initialized language model (e.g., ChatOpenAI).
        retriever: An initialized vector store retriever (e.g., from Qdrant).

    Yields:
        A stream of response chunks from the language model.
    """
    logger.info(
        "Starting RAG agent run", extra={"query": agent_input.query}
    )
    try:
        # Retrieve context first to enable context logging and verification
        retrieved_docs = await retriever.ainvoke(agent_input.query)
        logger.info(
            f"Retrieved {len(retrieved_docs)} documents",
            extra={"query": agent_input.query},
        )

        rag_chain = create_rag_chain(llm, retriever)

        # Stream the response from the chain
        async for chunk in rag_chain.astream(
            {"context": retrieved_docs, "question": agent_input.query}
        ):
            yield chunk

    except Exception as e:
        logger.error(
            "An error occurred during RAG agent execution",
            exc_info=True,
            extra={"query": agent_input.query},
        )
        # In a real application, you might yield a structured error message.
        yield json.dumps({"error": "An unexpected error occurred."})

if __name__ == "__main__":
    # This is a simple example of how to run the agent.
    # In a real application, these would be configured with actual services.
    from langchain_openai import ChatOpenAI
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings

    # 1. Mock Retriever
    docs = [
        Document(page_content="LangChain is a framework for building LLM applications."),
        Document(page_content="A RAG agent uses retrieval to augment generation."),
    ]
    vectorstore = FAISS.from_documents(docs, embedding=OpenAIEmbeddings())
    mock_retriever = vectorstore.as_retriever()

    # 2. Mock LLM
    mock_llm = ChatOpenAI(model="gpt-4o-mini") # Replace with your model

    # 3. Run Agent
    async def main():
        test_input = RAGInput(query="What is LangChain?")
        async for response_chunk in run_rag_agent(
            test_input, mock_llm, mock_retriever
        ):
            print(response_chunk, end="", flush=True)
        print()

    asyncio.run(main())