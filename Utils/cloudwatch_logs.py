import os
from dotenv import load_dotenv
import boto3
import logging
import watchtower

from logging import Logger

load_dotenv()

aws_default_region: str = os.environ["AWS_DEFAULT_REGION"]
environment: str  = os.environ['ENVIRONMENT']

log_group_name = f"{environment}-log-group-analysed-files"
cloudwatch_logs_client = boto3.client('logs', region_name=aws_default_region)

def create_cloudwatch_logger(log_group_name, log_stream_name) -> Logger:
    logger: Logger = logging.getLogger(f"{environment}/analyse_cloudwatch_logger/{log_stream_name}/{log_stream_name}")
    logger.setLevel(logging.INFO if environment == "prod" else logging.DEBUG) # set this to INFO for production later on

    handler = watchtower.CloudWatchLogHandler(
        log_group_name=log_group_name,
        stream_name=log_stream_name,
        create_log_group=True,      # Auto-create the log group if missing
        create_log_stream=True,     # Auto-create the stream if missing
        use_queues=True,            # Use background queue to batch-sent events
        send_interval=2,            # Flush every 2s in the background thread
        max_batch_size=1024 * 1024, # Default: 1MB
        max_batch_count=5000,      # Default: 10,000 events per batch
        max_message_size=256 * 1024,# Default: 256KB per message
        boto3_client=cloudwatch_logs_client,   # <-- Pass the client directly
    )
    logger.addHandler(handler)
    return logger
