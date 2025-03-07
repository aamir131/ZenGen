import os, json, boto3
from dotenv import load_dotenv

load_dotenv()

aws_default_region: str = os.environ["AWS_DEFAULT_REGION"]
environment: str  = os.environ['ENVIRONMENT']
current_directory = os.getcwd()

secret_client = boto3.client('secretsmanager', region_name=aws_default_region)

openai_api_key = json.loads(secret_client.get_secret_value(
            SecretId="dev/openAI"
        )['SecretString'])['dev/openAI']
helicone_api_key = json.loads(secret_client.get_secret_value(
            SecretId="dev/helicone"
)['SecretString'])['dev/helicone']
langfuse_public_key = json.loads(secret_client.get_secret_value(
            SecretId="prod/langfuse"
)['SecretString'])['LANGFUSE_PUBLIC_KEY']
langfuse_secret_key = json.loads(secret_client.get_secret_value(
            SecretId="prod/langfuse"
)['SecretString'])['LANGFUSE_SECRET_KEY']
slack_token  = json.loads(secret_client.get_secret_value(
            SecretId="dev/slack_bot_token"
)['SecretString'])['dev/slack_bot_token']
google_vertex_key = json.loads(secret_client.get_secret_value(
            SecretId="prod/google_test-282_service_account"
)['SecretString'])

google_api_key_file_path = os.path.join(current_directory, "google_api_key.json")
with open(google_api_key_file_path, 'w') as file:
    json.dump(google_vertex_key, file, indent=4)

if openai_api_key is None:
    raise Exception("OPENAI_API_KEY not found in environment variables")
if helicone_api_key is None:
    raise Exception("HELICONE_API_KEY not found in environment variables")
if environment is None:
    raise Exception("ENVIRONMENT not found in environment variables")
if langfuse_public_key is None:
    raise Exception("LANGFUSE_PUBLIC_KEY not found in environment variables")
if langfuse_secret_key is None:
    raise Exception("LANGFUSE_SECRET_KEY not found in environment variables")
if slack_token is None:
    raise Exception("SLACK_BOT_TOKEN not found in environment variables")
if google_vertex_key is None:
    raise Exception("GOOGLE_VERTEX_KEY not found in environment variables")

os.environ["OPENAI_API_KEY"] = openai_api_key
os.environ["LANGFUSE_PUBLIC_KEY"] = langfuse_public_key
os.environ["LANGFUSE_SECRET_KEY"] = langfuse_secret_key
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_api_key_file_path