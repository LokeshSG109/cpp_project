"""
smartnotifier.utils
----------------------
Low-level AWS SNS integration utility.
"""

def send_sns_message(sns_client, topic_arn, subject, message, priority):
    attrs = {"Priority": {"DataType": "String", "StringValue": priority}}
    sns_client.publish(
        TopicArn=topic_arn,
        Subject=subject,
        Message=message,
        MessageAttributes=attrs,
    )
