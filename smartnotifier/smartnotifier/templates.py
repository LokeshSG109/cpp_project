"""
smartnotifier.templates
----------------------
Provides message formatting for different priority levels.
"""

def get_message_template(priority, appointment):
    issue = appointment.get("issue", "")
    email = appointment.get("user_email", "")
    date = appointment.get("preferred_datetime", "")

    subject = f"[{priority}] Appointment {appointment['appointment_id']}"
    message = (
        f"New service request from {email}\n\n"
        f"Issue: {issue}\n"
        f"Preferred Time: {date}\n"
        f"Priority: {priority}\n"
        f"Status: {appointment.get('status', 'Pending')}\n"
    )
    return subject, message
