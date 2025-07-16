from typing import Dict, List, Any
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_core.documents import Document


class RAGInput(BaseModel):
    """Input schema for the RAG agent."""
    query: str = Field(..., description="The user's question.")
    chat_history: List[Dict[str, str]] = Field(
        default_factory=list, description="A list of previous messages in the conversation."
    )


def format_docs(docs: List[Document]) -> str:
    """Formats retrieved documents into a single string."""
    return "\n\n".join(doc.page_content for doc in docs)


def create_rag_chain(
    llm: BaseChatModel, retriever: VectorStoreRetriever
) -> Runnable[Dict, str]:
    """
    Creates the core RAG chain using LangChain's Runnable interface.

    The chain performs the following steps:
    1. Retrieves relevant documents from the vector store.
    2. Formats the documents and the user query into a prompt.
    3. Sends the prompt to the language model.
    4. Parses the model's output into a string.
    """
    # This prompt template is designed to ground the model's response in the provided context.
    template = """
    You are an assistant for question-answering tasks.
    Use the following pieces of retrieved context to answer the question.
    If you don't know the answer, just say that you don't know.
    Keep the answer concise.

    Context:
    {context}

    Question:
    {question}

    Answer:
    """
    prompt = ChatPromptTemplate.from_template(template)

    # The LCEL chain definition
    rag_chain = (
        RunnablePassthrough.assign(context=(lambda x: format_docs(x["context"])))
        | prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain