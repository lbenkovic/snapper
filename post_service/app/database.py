import os
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

# Check AWS credentials
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")

if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
    raise RuntimeError("AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY environment variable is not set.")

dynamodb = boto3.resource(
    "dynamodb",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION,
)

table_name = "Posts"
posts_table = dynamodb.Table(table_name)

# Enable TTL on the table
def enable_ttl(table_name: str, ttl_attribute: str = "expires_at"):
    client = boto3.client(
        "dynamodb",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )
    try:
        desc = client.describe_time_to_live(TableName=table_name)
        if desc["TimeToLiveDescription"]["TimeToLiveStatus"] == "ENABLED":
            print(f"TTL already enabled on '{table_name}'.")
            return
    except ClientError as e:
        print(f"TTL error: {e}")
        
    try:
        client.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={
                "Enabled": True,
                "AttributeName": ttl_attribute
            }
        )
        print(f"TTL enabled on '{table_name}' using attribute '{ttl_attribute}'.")
    except ClientError as e:
        print(f"Enable TTL error: {e}")

# Create Posts table if it doesn't exist
def create_table():
    try:
        existing_tables = [table.name for table in dynamodb.tables.all()]
        if table_name not in existing_tables:
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "post_id", "KeyType": "HASH"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "post_id", "AttributeType": "S"},
                    {"AttributeName": "username", "AttributeType": "S"},
                    {"AttributeName": "created_at", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "username-created_at-index",
                        "KeySchema": [
                            {"AttributeName": "username", "KeyType": "HASH"},
                            {"AttributeName": "created_at", "KeyType": "RANGE"}
                        ],
                        "Projection": {"ProjectionType": "ALL"}
                    }
                ],
                BillingMode="PAY_PER_REQUEST"
            )
            
            print(f"Table '{table_name}' created.")
            
            table.wait_until_exists()
            
            print(f"Table '{table_name}' ready to use.")
            
            enable_ttl(table_name)
        else:
            print(f"Table '{table_name}' already exists.")
            enable_ttl(table_name)
    except ClientError as e:
        print(f"Create table error: {e}")