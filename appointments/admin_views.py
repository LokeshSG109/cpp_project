# appointments/admin_views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from smartnotifier import SmartNotifier
import boto3, os


from . import aws_utils

# Allow only superusers/staff
def admin_check(user):
    return user.is_staff or user.is_superuser


@user_passes_test(admin_check)
def admin_dashboard(request):
    """
    List all appointments stored in DynamoDB.
    """
    # fetch all appointments from DynamoDB
    try:
        data = aws_utils.appointments_table.scan()
        appointments = data.get("Items", [])
        # sort by creation date if exists
        appointments.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    except Exception as e:
        messages.error(request, f"Error loading appointments: {e}")
        appointments = []

    return render(request, "appointments/admin_dashboard.html", {"appointments": appointments})


# @user_passes_test(admin_check)
# def update_status(request, appointment_id):
#     """
#     Update appointment status in DynamoDB.
#     """
#     if request.method == "POST":
#         new_status = request.POST.get("status")
#         try:
#             aws_utils.appointments_table.update_item(
#                 Key={"appointment_id": appointment_id},
#                 UpdateExpression="SET #s = :new_status",
#                 ExpressionAttributeNames={"#s": "status"},
#                 ExpressionAttributeValues={":new_status": new_status},
#             )
#             messages.success(request, f"Appointment {appointment_id} updated to {new_status}")
#         except Exception as e:
#             messages.error(request, f"Error updating status: {e}")

#     return redirect(reverse("appointments:admin_dashboard"))

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

            # ✅ Notify using SmartNotifier
            sns_client = boto3.client("sns", region_name=settings.AWS_REGION)
            notifier = SmartNotifier.notify(sns_client, settings.SNS_ADMIN_TOPIC_ARN)

            response = aws_utils.appointments_table.get_item(Key={"appointment_id": appointment_id})
            appointment = response.get("Item")
            if appointment:
                notifier.notify(appointment)

            messages.success(request, f"Appointment {appointment_id} updated to {new_status}")
        except Exception as e:
            messages.error(request, f"Error updating status: {e}")

    return redirect(reverse("appointments:admin_dashboard"))

