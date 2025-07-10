"""Email agent that uses the Gmail tool."""

from pydantic_ai import PydanticAI
from pydantic_ai.llm.openai import OpenAI
from tools.gmail_tool import gmail_tool
from agents.models import EmailDraft

# It's a good practice to define the agent's task clearly.
EMAIL_AGENT_TASK = "You are an agent that is an expert at composing and sending emails. You will be given the recipient, subject, and body of an email and you will create a draft."


def get_email_agent(llm_provider: OpenAI) -> PydanticAI:
    """
    Factory function to create an email agent.

    Args:
        llm_provider: An instance of an OpenAI provider.

    Returns:
        A PydanticAI agent configured to handle email tasks.
    """
    email_agent = PydanticAI(
        llm=llm_provider,
        task=EMAIL_AGENT_TASK,
        input_model=EmailDraft,
    )
    email_agent.register_tool(gmail_tool)
    return email_agent
