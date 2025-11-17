import os, json
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
import uuid
import time
from boto3.dynamodb.conditions import Attr
from django.conf import settings

AWS_REGION = settings.AWS_REGION

def get_secret():

    secret_name = settings.SECRETS_NAME
    region_name = AWS_REGION

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e

    secret = get_secret_value_response['SecretString']
    secret_dict = json.loads(secret)

    return secret_dict

secret = get_secret()

S3_BUCKET = secret["S3_BUCKET"]
DDB_USERS_TABLE = secret["DDB_USERS_TABLE"]
DDB_APPOINTMENTS_TABLE = secret["DDB_APPOINTMENTS_TABLE"]
SQS_QUEUE_URL = secret["SQS_APPOINTMENTS_QUEUE_URL"]
SNS_USER_TOPIC_ARN = secret["SNS_USER_TOPIC_ARN"]

session = boto3.Session(region_name=AWS_REGION)
s3 = session.client("s3")
sqs = session.client("sqs")
sns = session.client("sns")
dynamodb = session.resource("dynamodb")
users_table = dynamodb.Table(DDB_USERS_TABLE)
appointments_table = dynamodb.Table(DDB_APPOINTMENTS_TABLE)

def create_user(email: str, password_hash: str, full_name: str):
    user_id = str(uuid.uuid4())
    item = {
        "user_id": user_id,
        "email": email.lower(),
        "password_hash": password_hash,
        "full_name": full_name,
        "created_at": int(time.time()),
    }
    users_table.put_item(Item=item)
    return item

def get_user_by_email(email: str):
    resp = users_table.get_item(Key={"email": email.lower()})
    return resp.get("Item")

def create_appointment(user_id: str, user_email: str, issue: str, preferred_datetime: str, s3_photos: list):
    appointment_id = str(uuid.uuid4())
    item = {
        "appointment_id": appointment_id,
        "user_id": user_id,
        "user_email": user_email,
        "issue": issue,
        "preferred_datetime": preferred_datetime,
        "s3_photos": s3_photos,
        "status": "PENDING",
        "created_at": int(time.time()),
    }
    appointments_table.put_item(Item=item)
    return item

def get_appointments_for_user(user_id: str):

    """
    Fetch appointments for a specific user.
    Uses a Scan + FilterExpression (fine for small datasets / demo projects).
    For production, create a GSI on 'user_id' and use query instead.
    """
    try:
        response = appointments_table.scan(
            FilterExpression=Attr("user_id").eq(user_id)
        )
        return response.get("Items", [])
    except Exception as e:
        print(f"Error fetching appointments: {e}")
        return []

def upload_file_to_s3(file_obj, key: str, content_type: str):
    try:
        s3.upload_fileobj(
            Fileobj=file_obj,
            Bucket=S3_BUCKET,
            Key=key,
            ExtraArgs={"ACL": "private", "ContentType": content_type}
        )
        return f"s3://{S3_BUCKET}/{key}"
    except ClientError as e:
        raise

def generate_s3_key(filename: str):
    return f"appointment_photos/{uuid.uuid4()}_{filename}"


def send_appointment_message_to_sqs(appointment_item: dict):
    if not SQS_QUEUE_URL:
        return None
    resp = sqs.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=str(appointment_item),
        MessageAttributes={
            "appointment_id": {"DataType": "String", "StringValue": appointment_item["appointment_id"]},
            "user_email": {"DataType": "String", "StringValue": appointment_item["user_email"]}
        }
    )
    return resp


def publish_sns_notification(subject: str, message: str, attributes: dict = None):
    if not SNS_USER_TOPIC_ARN:
        return None
    resp = sns.publish(TopicArn=SNS_USER_TOPIC_ARN, Subject=subject, Message=message, MessageAttributes=attributes or {})
    return resp

import hashlib

def hash_password(password: str) -> str:
    """
    Returns a SHA-256 hash of the password with a fixed salt.
    Note: For demonstration only. In production, use Django's built-in User model and PBKDF2/Bcrypt.
    """
    salt = "nci_salt_2025"
    hashed = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return hashed