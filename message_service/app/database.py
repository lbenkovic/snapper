import os
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

# Check AWS credentials
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
    raise RuntimeError("AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY environment variable is not set.")

dynamodb = boto3.resource(
    "dynamodb",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

table_name = "Messages"
messages_table = dynamodb.Table(table_name)  # type: ignore

# Create messages table if it doesn't exist
def create_table():
    try:
        existing_tables = [t.name for t in dynamodb.tables.all()]  # type: ignore
        if table_name not in existing_tables:
            table = dynamodb.create_table( #type: ignore
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "conversation_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"}
                ],
                AttributeDefinitions=[
                    {"AttributeName": "conversation_id", "AttributeType": "S"},
                    {"AttributeName": "created_at", "AttributeType": "S"},
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

# Enable ttl on the table
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
