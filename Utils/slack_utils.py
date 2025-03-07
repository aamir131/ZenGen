import os
from dotenv import load_dotenv

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from Utils.secrets import slack_token

load_dotenv()

environment = os.environ['ENVIRONMENT']
slack_channel_name = f"#{environment}-alerts"

slack_client = WebClient(token=slack_token)

def send_message_to_slack(message: str):
    try:
        response = slack_client.chat_postMessage(
            channel=slack_channel_name,
            text=message
        )
        return response
    except SlackApiError as e:
        print(f"[ERROR] Failed sending message to Slack: {e.response['error']}")
        raise e

def send_document_alert_to_slack(title: str, stage: str, document_url: str | None, user_defined_file_name: str, pdf_s3_file_name: str, file_hash: str,
                                 user_email: str | None, pdf_page_count: int, cloudwatch_url: str, s3_storage_bucket_urls: list[str] | None):
    send_message_to_slack(
        (f"{title}\n") +
        (f"Stage: *{stage}*\n") +
        (f"File name: <{document_url}|{user_defined_file_name}>\n" if document_url else f'{user_defined_file_name}\n') +
        (f"File Hash: {file_hash}\n") +
        (f"textract_id: {pdf_s3_file_name}\n") +
        (f"User: {user_email}\n") +
        (f"Page count: {pdf_page_count}\n") +
        (f"Cloudwatch: <{cloudwatch_url}|CloudWatchLogs>\n") +
        (f"Buckets: {' | '.join(s3_storage_bucket_urls)}\n" if s3_storage_bucket_urls else ""),
    )