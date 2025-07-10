"""Tool for interacting with the Gmail API."""

import os.path
import sys
from pathlib import Path
import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.models import EmailDraft

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
CREDENTIALS_FILE = "credentials/credentials.json"
TOKEN_FILE = "credentials/token.json"


def get_gmail_service():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except ValueError:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_FILE}' not found. Please download your "
                    "OAuth 2.0 client secrets file from the Google Cloud "
                    "Console and save it in the 'credentials' directory."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(host="127.0.0.1", port=8080)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def create_draft(service, draft: EmailDraft):
    """Create and insert a draft email.
    Print the returned draft's message and id.
    Returns: Draft object, including draft id and message meta data.
    """
    try:
        message = MIMEText(draft.body)
        message["to"] = ", ".join(draft.to)
        message["subject"] = draft.subject
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {"message": {"raw": encoded_message}}
        draft = (
            service.users().drafts().create(userId="me", body=create_message).execute()
        )
        print(f'Draft id: {draft["id"]}\nDraft message: {draft["message"]}')
        return draft
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


async def gmail_tool(draft: EmailDraft) -> str:
    """
    Creates a draft email in Gmail.

    Args:
        draft: An EmailDraft object containing the recipient, subject, and body.

    Returns:
        A string indicating the result of the operation.
    """
    service = get_gmail_service()
    result = create_draft(service, draft)
    if result:
        return f"Successfully created draft with ID: {result['id']}"
    else:
        return "Failed to create draft."


if __name__ == "__main__":
    # This block will be executed when the script is run directly.
    # It will initiate the OAuth2 flow and create the token.json file.
    print("Attempting to get Gmail service to initiate OAuth2 flow if necessary...")
    get_gmail_service()
    print(
        "Gmail service obtained. If this was the first run, token.json should now be created."
    )
