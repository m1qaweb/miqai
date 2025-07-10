from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import Runnable, RunnablePassthrough, RunnableLambda
from langchain.schema.output_parser import StrOutputParser
from insight_engine.tools.vector_store import VectorStore
from typing import List

class SummarizationAgent:
    """
    An agent that uses a Retrieval-Augmented Generation (RAG) chain
    to produce context-grounded summaries.
    """

    def __init__(self, vector_store: VectorStore):
        """
        Initializes the SummarizationAgent.

        Args:
            vector_store: An instance of the VectorStore service.
        """
        self.vector_store = vector_store
        
        # 1. Create a retriever from the VectorStore instance
        # We wrap the async query method in a RunnableLambda to make it
        # compatible with the LangChain Expression Language (LCEL).
        retriever = RunnableLambda(self.vector_store.query)

        # 2. Define the prompt template
        template = """Answer the user's question based on the following context:
        
        Context:
        {context}
        
        Question:
        {question}
        """
        prompt = ChatPromptTemplate.from_template(template)

        # 3. Instantiate the language model
        model = ChatGoogleGenerativeAI(model="gemini-pro")

        # 4. Define a function to format the retrieved documents
        def format_docs(docs: List[str]) -> str:
            return "\n\n".join(docs)

        # 5. Construct the RAG chain using LCEL
        self.rag_chain: Runnable = (
            {
                "context": retriever | format_docs,
                "question": RunnablePassthrough()
            }
            | prompt
            | model
            | StrOutputParser()
        )

    async def generate_summary(self, question: str) -> str:
        """
        Invokes the RAG chain with the user's question to generate a summary.

        Args:
            question: The user's question or topic for summarization.

        Returns:
            The content of the AI's response as a string.
        """
        response = await self.rag_chain.ainvoke(question)
        return response
