from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from smartnotifier import SmartNotifier
import boto3, os
from . import aws_utils


secret = aws_utils.get_secret()

def admin_check(user):
    return user.is_staff or user.is_superuser


@user_passes_test(admin_check)
def admin_dashboard(request):
    """
    List all appointments stored in DynamoDB.
    """
    try:
        data = aws_utils.appointments_table.scan()
        appointments = data.get("Items", [])
        appointments.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    except Exception as e:
        appointments = []

    return render(request, "appointments/admin_dashboard.html", {"appointments": appointments})

@user_passes_test(admin_check)
def update_status(request, appointment_id):
    if request.method == "POST":
        new_status = request.POST.get("status")
        try:
            aws_utils.appointments_table.update_item(
                Key={"appointment_id": appointment_id},
                UpdateExpression="SET #s = :new_status",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":new_status": new_status},
            )

            sns_client = boto3.client("sns", region_name=settings.AWS_REGION)
            notifier = SmartNotifier.notify(sns_client, secret["SNS_ADMIN_TOPIC_ARN"])

            response = aws_utils.appointments_table.get_item(Key={"appointment_id": appointment_id})
            appointment = response.get("Item")
            if appointment:
                notifier.notify(appointment)

        except Exception as e:
            pass

    return redirect(reverse("appointments:admin_dashboard"))

