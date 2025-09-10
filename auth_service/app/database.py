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

table_name = "Users"
users_table = dynamodb.Table(table_name)

# Create users table if it doesn't exist
def create_table():
    try:
        existing_tables = [table.name for table in dynamodb.tables.all()]
        if table_name not in existing_tables:
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "username", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST"
            )
            
            print(f"Table '{table_name}' created.")
            
            table.wait_until_exists()
            
            print(f"Table '{table_name}' ready to use.")
        else:
            print(f"Table '{table_name}' already exists.")
    except ClientError as e:
        print(f"Create table error: {e}")