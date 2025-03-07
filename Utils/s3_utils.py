import os, io, json, boto3, base64, hashlib
from enum import Enum
from collections import namedtuple

from PIL import Image
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

environment: str = os.environ['ENVIRONMENT']
version: str = os.environ['VERSION']
aws_default_region: str = os.environ["AWS_DEFAULT_REGION"]
s3_client = boto3.client('s3', region_name=aws_default_region)

StorageBucketInfo = namedtuple('StorageBucketInfo', ['name', 'url_link'])

class s3_storage_buckets(Enum):
    s3_init_parsing_bucket = StorageBucketInfo(
        name = f"{environment}-s3-init-parsing-london",
        url_link = lambda file_hash: f"https://s3.console.aws.amazon.com/s3/buckets/{environment}-s3-init-parsing-london?region={aws_default_region}&prefix={file_hash}/versions/{version}/"
    )

    s3_llm_parsing_bucket = StorageBucketInfo(
        name = f"{environment}-s3-llm-parsing-london",
        url_link = lambda pdf_s3_file_name: f"https://s3.console.aws.amazon.com/s3/buckets/{environment}-s3-llm-parsing-london?region={aws_default_region}&prefix={pdf_s3_file_name}/versions/{version}/"
    )

    s3_datapoint_generation_bucket = StorageBucketInfo(
        name = f"{environment}-s3-datapoint-generation-london",
        url_link = lambda pdf_s3_file_name: f"https://s3.console.aws.amazon.com/s3/buckets/{environment}-s3-datapoint-generation-london?region={aws_default_region}&prefix={pdf_s3_file_name}/versions/{version}/"
    )

    s3_router_bucket = StorageBucketInfo(
        name = f"{environment}-s3-router-london",
        url_link = lambda pdf_s3_file_name: f"https://s3.console.aws.amazon.com/s3/buckets/{environment}-s3-router-london?region={aws_default_region}&prefix={pdf_s3_file_name}/versions/{version}/"
    )

    s3_uploads_bucket = StorageBucketInfo(
        name = f"{environment}-s3-uploads-london",
        url_link = lambda pdf_s3_file_name: f"https://s3.console.aws.amazon.com/s3/buckets/{environment}-s3-uploads-london?region={aws_default_region}&prefix={pdf_s3_file_name}"
    )

def write_dict_to_s3(s3_bucket: s3_storage_buckets, s3_file_name: str, s3_key: str, data: dict | list):
    # Create the full path by combining the folder and file name if a folder is specified
    if s3_key:
        s3_file_path = f"{s3_key.rstrip('/')}/{s3_file_name}"  # Ensure no double slashes
    else:
        s3_file_path = s3_file_name

    # Write JSON string to the specified S3 bucket and file path
    json_data = json.dumps(data, indent=4, default=str)
    s3_client.put_object(Bucket=s3_bucket.value.name, Key=s3_file_path, Body=json_data)

def read_dict_from_s3(s3_bucket: s3_storage_buckets, key: str, file_to_read) -> dict:
    s3_key = f"{key}/{file_to_read}" if key else file_to_read
    try:
        response = s3_client.get_object(Bucket=s3_bucket.value.name, Key=s3_key)
        file_content = response['Body'].read().decode('utf-8')
        return json.loads(file_content)
    except Exception as e:
        print(f"[ERROR] reading file from S3: {e}")
        raise e

def save_png_to_s3(s3_bucket: s3_storage_buckets, key: str, filename: str, image_data):
    """Helper function to save image data to S3."""
    if not image_data:
        return False

    key = f"{key}/{filename}"
    s3_client.put_object(
        Bucket=s3_bucket.value.name,
        Key=key,
        Body=image_data,
        ContentType='image/png'
    )
    return True

def get_image_from_s3(bucket: s3_storage_buckets, key: str) -> str:
    """Fetch an image from S3 and return its compressed base64 encoded string."""
    try:
        image_data = s3_client.get_object(Bucket=bucket.value.name, Key=key)['Body'].read()
        img = Image.open(io.BytesIO(image_data))

        with io.BytesIO() as buffer:
            img.save(buffer, format='PNG', optimize=True, quality=85)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[ERROR] Error processing image from S3: {e}")
        raise e

def get_image_object_from_s3(bucket: s3_storage_buckets, key: str):
    image_data = s3_client.get_object(Bucket=bucket.value.name, Key=key)['Body'].read()
    return Image.open(io.BytesIO(image_data))

def get_image_from_local_file(file_path: str) -> str:
    """Fetch an image from a local file and return its compressed base64 encoded string."""
    try:
        with open(file_path, 'rb') as image_file:
            image_data = image_file.read()
            with io.BytesIO() as buffer:
                img = Image.open(io.BytesIO(image_data))
                img.save(buffer, format='PNG', optimize=True, quality=85)
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[ERROR] Error processing image from local file: {e}")
        raise e
    

def file_exists_in_s3_bucket(bucket: s3_storage_buckets, file_key: str):
    try:
        return s3_client.head_object(Bucket=bucket.value.name, Key=file_key)
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        else:
            raise e

def generate_s3_file_hash(bucket: s3_storage_buckets, file_key: str):
    hash_func = hashlib.new('sha256')

    obj = s3_client.get_object(Bucket=bucket.value.name, Key=file_key)
    for chunk in obj['Body'].iter_chunks(chunk_size=8192):
        hash_func.update(chunk)

    return hash_func.hexdigest()