
import json
import os
import boto3

from appointments import aws_utils

secret = aws_utils.get_secret()

SNS_TOPIC_ARN = secret["SNS_USER_TOPIC_ARN"]
sns = boto3.client("sns")
dynamodb = boto3.resource("dynamodb")
DDB_APPOINTMENTS_TABLE = secret["DDB_APPOINTMENTS_TABLE"]

def lambda_handler(event, context):
    results = []
    for record in event.get("Records", []):
        body = record.get("body")  
        try:
            
            try:
                appointment = json.loads(body)
            except Exception:
                
                appointment = eval(body)
            
            table = dynamodb.Table(DDB_APPOINTMENTS_TABLE)
            table.update_item(
                Key={"appointment_id": appointment["appointment_id"]},
                UpdateExpression="SET #s = :new",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":new": "RECEIVED_BY_QUEUE"}
            )
            
            subj = f"New Appointment Received: {appointment['appointment_id']}"
            msg = f"Appointment for {appointment['user_email']} regarding {appointment['issue']} at {appointment['preferred_datetime']}"
            sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subj, Message=msg)
            results.append({"appointment_id": appointment.get("appointment_id"), "status": "processed"})
        except Exception as e:
            results.append({"error": str(e)})
    return {"results": results}
