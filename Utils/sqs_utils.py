import os
from dotenv import load_dotenv

import boto3

load_dotenv()

environment = os.environ['ENVIRONMENT']
aws_default_region: str = os.environ['AWS_DEFAULT_REGION']

sqs_queue_url = f"https://sqs.eu-west-2.amazonaws.com/004167031409/{environment}-analyse-sqs"
sqs_client = boto3.client('sqs', region_name=aws_default_region)