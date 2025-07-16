import os
import json
import requests

def send_slack_notification(request):
    """
    Sends a notification to a Slack channel.
    """
    slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not slack_webhook_url:
        return "SLACK_WEBHOOK_URL not set.", 500

    message = request.get_json().get("message")
    if not message:
        return "No message provided.", 400

    payload = {"text": message}
    try:
        requests.post(slack_webhook_url, json=payload)
        return "Notification sent.", 200
    except Exception as e:
        return f"Error sending notification: {e}", 500
