"""
A reusable notification management library that decides
how and when to notify users or engineers based on appointment data.
"""

import datetime
from .priority import calculate_priority
from .templates import get_message_template
from .utils import send_sns_message


class SmartNotifier:
    def __init__(self, sns_client, topic_arn):
        self.sns = sns_client
        self.topic_arn = topic_arn

    def notify(self, appointment):
        issue = appointment.get("issue", "").lower()
        preferred_time = appointment.get("preferred_datetime", "")
        user_email = appointment.get("user_email", "")
        appt_id = appointment.get("appointment_id", "")

        priority = calculate_priority(issue, preferred_time)

        subject, message = get_message_template(priority, appointment)

        send_sns_message(self.sns, self.topic_arn, subject, message, priority)

        return {
            "appointment_id": appt_id,
            "priority": priority,
            "status": "sent"
        }
