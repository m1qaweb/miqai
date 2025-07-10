"""Research agent that uses the Brave Search tool and the Email agent."""

from pydantic_ai import PydanticAI
from pydantic_ai.llm.openai import OpenAI
from tools.brave_search import brave_search_tool
from agents.email_agent import get_email_agent
from agents.models import BraveSearchResult, EmailDraft

# Define the research agent's task.
RESEARCH_AGENT_TASK = (
    "You are a research assistant. Your goal is to use the Brave Search tool to find "
    "information on a given topic. After gathering the information, you will delegate "
    "the task of composing a summary email to the email agent."
)


def get_research_agent(llm_provider: OpenAI) -> PydanticAI:
    """
    Factory function to create a research agent.

    Args:
        llm_provider: An instance of an OpenAI provider.

    Returns:
        A PydanticAI agent configured for research tasks.
    """
    # The research agent needs to know about the data models it might encounter.
    research_agent = PydanticAI(
        llm=llm_provider,
        task=RESEARCH_AGENT_TASK,
        input_model=BraveSearchResult,
        output_model=EmailDraft,
    )

    # Register the tools the agent can use.
    research_agent.register_tool(brave_search_tool)

    # Here, we register the email agent as a tool for the research agent.
    # This is a simple way to achieve agent-to-agent communication.
    email_agent = get_email_agent(llm_provider)
    research_agent.register_tool(email_agent.run, "email_agent_tool")

    return research_agent
