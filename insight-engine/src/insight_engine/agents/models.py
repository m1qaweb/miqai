"""Pydantic models for the multi-agent system."""

from pydantic import BaseModel, Field
from typing import List


class BraveSearchResult(BaseModel):
    """Data model for a single Brave search result."""

    title: str = Field(..., description="The title of the search result.")
    url: str = Field(..., description="The URL of the search result.")
    description: str = Field(
        ..., description="A brief description of the search result."
    )


class EmailDraft(BaseModel):
    """Data model for an email draft."""

    to: List[str] = Field(..., description="A list of recipient email addresses.")
    subject: str = Field(..., description="The subject of the email.")
    body: str = Field(..., description="The body of the email.")
