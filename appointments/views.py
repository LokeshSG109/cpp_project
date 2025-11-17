import hashlib, datetime
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from .forms import RegisterForm, LoginForm, AppointmentForm
from . import aws_utils
from smartnotifier import SmartNotifier
import boto3, os
from django.contrib.auth.decorators import login_required

def hash_password(password: str):
    salt = "nci_salt_2025"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

def login_user(request, user_item):
    request.session["user_id"] = user_item["user_id"]
    request.session["user_email"] = user_item["email"]
    request.session["full_name"] = user_item.get("full_name", "")

def logout_user(request):
    request.session.flush()

def current_user(request):
    uid = request.session.get("user_id")
    email = request.session.get("user_email")
    if not uid:
        return None
    return {"user_id": uid, "email": email, "full_name": request.session.get("full_name")}

def index(request):
    user = current_user(request)
    return render(request, "appointments/dashboard.html", {"user": user})

# def register_view(request):
#     if request.method == "POST":
#         form = RegisterForm(request.POST)
#         if form.is_valid():
#             data = form.cleaned_data
#             if aws_utils.get_user_by_email(data["email"]):
#                 form.add_error("email", "Email already registered")
#             else:
#                 password_hash = hash_password(data["password"])
#                 user_item = aws_utils.create_user(data["email"], password_hash, data["full_name"])
#                 login_user(request, user_item)
#                 messages.success(request, "Registration successful.")
#                 return redirect(reverse("appointments:dashboard"))
#     else:
#         form = RegisterForm()
#     return render(request, "appointments/register.html", {"form": form})

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data

            # Check if email already exists
            if aws_utils.get_user_by_email(data["email"]):
                form.add_error("email", "Email already registered")
                return render(request, "appointments/register.html", {"form": form})

            # Save user in DynamoDB
            password_hash = aws_utils.hash_password(data["password"])
            user_item = aws_utils.create_user(
                email=data["email"],
                password_hash=password_hash,
                full_name=data["full_name"],
            )

            # ✅ Step 1: Subscribe user to SNS topic
            sns_client = boto3.client("sns", region_name=settings.AWS_REGION)
            try:
                response = sns_client.subscribe(
                    TopicArn=settings.SNS_USER_TOPIC_ARN,
                    Protocol="email",
                    Endpoint=data["email"],
                    ReturnSubscriptionArn=False,  # AWS sends a confirmation email
                )
                print(f"✅ Subscription initiated for {data['email']}: {response}")
            except Exception as e:
                print(f"❌ Error subscribing user to SNS: {e}")

            # ✅ Step 2: Log the user in immediately
            login_user(request, user_item)
            messages.success(
                request,
                "Registration successful! Please check your email to confirm your SNS subscription."
            )
            return redirect(reverse("appointments:dashboard"))
    else:
        form = RegisterForm()
    return render(request, "appointments/register.html", {"form": form})

def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            user_item = aws_utils.get_user_by_email(email)
            if not user_item:
                form.add_error("email", "User not found")
            else:
                if user_item["password_hash"] != hash_password(password):
                    form.add_error("password", "Incorrect password")
                else:
                    login_user(request, user_item)
                    messages.success(request, "Logged in successfully.")
                    return redirect(reverse("appointments:dashboard"))
    else:
        form = LoginForm()
    return render(request, "appointments/login.html", {"form": form})

# def login_view(request):
#     if request.method == "POST":
#         form = LoginForm(request.POST)
#         if form.is_valid():
#             email = form.cleaned_data["email"]
#             password = form.cleaned_data["password"]

#             user_item = aws_utils.get_user_by_email(email)
#             if not user_item:
#                 form.add_error("email", "User not found")
#             elif user_item["password_hash"] != hash_password(password):
#                 form.add_error("password", "Incorrect password")
#             else:
#                 login_user(request, user_item)

#                 name = user_item.get("full_name", "").lower()
#                 if (
#                     user_item.get("is_admin")
#                     or name == "admin"
#                     or email.lower().startswith("admin")
#                 ):
#                     messages.success(request, f"Welcome back, {user_item['full_name']} (Admin)")
#                     return redirect(reverse("appointments:admin_dashboard"))

#                 messages.success(request, "Logged in successfully.")
#                 return redirect(reverse("appointments:dashboard"))
#     else:
#         form = LoginForm()
#     return render(request, "appointments/login.html", {"form": form})


# def dashboard_view(request):
#     user = current_user(request)
#     if not user:
#         return redirect(reverse("appointments:login"))

#     if (
#         user.get("is_admin")
#         or user.get("full_name", "").lower() == "admin"
#         or user.get("email", "").lower().startswith("admin")
#     ):
#         return redirect(reverse("appointments:admin_dashboard"))

#     appointments = aws_utils.get_appointments_for_user(user["user_id"])
#     return render(request, "appointments/dashboard.html", {"user": user, "appointments": appointments})


def logout_view(request):
    logout_user(request)
    messages.success(request, "Logged out.")
    return redirect(reverse("appointments:login"))

def dashboard_view(request):
    user = current_user(request)
    if not user:
        return redirect(reverse("appointments:login"))
    appointments = aws_utils.get_appointments_for_user(user["user_id"])
    return render(request, "appointments/dashboard.html", {"user": user, "appointments": appointments})

# def book_view(request):
#     user = current_user(request)
#     if not user:
#         return redirect(reverse("appointments:login"))
#     if request.method == "POST":
#         form = AppointmentForm(request.POST, request.FILES)
#         if form.is_valid():
#             data = form.cleaned_data
#             s3_photos = []
#             files = request.FILES.getlist("photos")
#             print("FILES:", request.FILES)
#             for f in files:
#                 # print("FILES:", request.FILES)
#                 key = aws_utils.generate_s3_key(f.name)
#                 aws_utils.upload_file_to_s3(f, key, f.content_type)
#                 s3_photos.append(f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}")
#             appt = aws_utils.create_appointment(user_id=user["user_id"], user_email=user["email"], issue=data["issue"], preferred_datetime=data["preferred_datetime"], s3_photos=s3_photos)
#             aws_utils.send_appointment_message_to_sqs(appt)
#             messages.success(request, "Appointment booked. Our team will contact you.")
#             return redirect(reverse("appointments:dashboard"))
#     else:
#         form = AppointmentForm()
#     return render(request, "appointments/book.html", {"user": user, "form": form})

# def book_view(request):
#     user = current_user(request)
#     if not user:
#         return redirect(reverse("appointments:login"))

#     if request.method == "POST":
#         form = AppointmentForm(request.POST, request.FILES)
#         print("DEBUG FILES:", request.FILES)

#         if form.is_valid():
#             data = form.cleaned_data
#             s3_photos = []

#             # Get list of uploaded photos
#             files = request.FILES.getlist("photos")
#             for f in files:
#                 key = aws_utils.generate_s3_key(f.name)
#                 aws_utils.upload_file_to_s3(f, key, f.content_type)
#                 s3_photos.append(
#                     f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
#                 )

#             # Save appointment and send to SQS
#             appt = aws_utils.create_appointment(
#                 user_id=user["user_id"],
#                 user_email=user["email"],
#                 issue=data["issue"],
#                 preferred_datetime=data["preferred_datetime"],
#                 s3_photos=s3_photos,
#             )
#             aws_utils.send_appointment_message_to_sqs(appt)
#             messages.success(request, "Appointment booked. Our team will contact you.")
#             return redirect(reverse("appointments:dashboard"))
#         else:
#             # Form not valid → re-render the same page with errors visible
#             messages.error(request, "Please correct the errors below.")
#             return render(request, "appointments/book.html", {"user": user, "form": form})

#     # GET request → display a new blank form
#     form = AppointmentForm()
#     return render(request, "appointments/book.html", {"user": user, "form": form})

# def book_view(request):
#     user = current_user(request)
#     if not user:
#         return redirect(reverse("appointments:login"))

#     if request.method == "POST":
#         form = AppointmentForm(request.POST, request.FILES)
#         if form.is_valid():
#             data = form.cleaned_data
#             s3_photos = []

#             files = request.FILES.getlist("photos")
#             for f in files:
#                 key = aws_utils.generate_s3_key(f.name)
#                 aws_utils.upload_file_to_s3(f, key, f.content_type)
#                 s3_photos.append(
#                     f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
#                 )

#             # Save appointment in DynamoDB
#             appt = aws_utils.create_appointment(
#                 user_id=user["user_id"],
#                 user_email=user["email"],
#                 issue=data["issue"],
#                 preferred_datetime=data["preferred_datetime"],
#                 s3_photos=s3_photos,
#             )

#             # Send to SQS for async processing
#             aws_utils.send_appointment_message_to_sqs(appt)

#             # ✅ NEW: Send smart notification using your library
#             sns_client = boto3.client("sns", region_name=os.getenv("AWS_REGION"))
#             notifier = smartnotifier.SmartNotifier(sns_client, os.getenv("SNS_TOPIC_ARN"))
#             result = notifier.notify(appt)

#             print("Notification Sent:", result)

#             messages.success(request, "Appointment booked and notification sent!")
#             return redirect(reverse("appointments:dashboard"))
#         else:
#             messages.error(request, "Please correct the errors below.")
#     else:
#         form = AppointmentForm()

#     return render(request, "appointments/book.html", {"user": user, "form": form})

def book_view(request):
    user = current_user(request)
    if not user:
        return redirect(reverse("appointments:login"))

    if request.method == "POST":
        form = AppointmentForm(request.POST, request.FILES)
        # if form.is_valid():
        #     data = form.cleaned_data
        #     s3_photos = []

        #     files = request.FILES.getlist("photos")
        #     for f in files:
        #         key = aws_utils.generate_s3_key(f.name)
        #         aws_utils.upload_file_to_s3(f, key, f.content_type)
        #         s3_photos.append(
        #             f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
        #         )

        #     # Save appointment in DynamoDB
        #     appt = aws_utils.create_appointment(
        #         user_id=user["user_id"],
        #         user_email=user["email"],
        #         issue=data["issue"],
        #         preferred_datetime=data["preferred_datetime"],
        #         s3_photos=s3_photos,
        #     )

        if form.is_valid():
            data = form.cleaned_data
            s3_photos = []

            # ✅ Convert datetime object to string for DynamoDB
            preferred_dt = data["preferred_datetime"]
            if isinstance(preferred_dt, (datetime.datetime, datetime.date)):
                preferred_dt = preferred_dt.strftime("%Y-%m-%d %H:%M:%S")

            files = request.FILES.getlist("photos")
            for f in files:
                key = aws_utils.generate_s3_key(f.name)
                aws_utils.upload_file_to_s3(f, key, f.content_type)
                s3_photos.append(
                    f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
                )

            # Save appointment in DynamoDB
            appt = aws_utils.create_appointment(
                user_id=user["user_id"],
                user_email=user["email"],
                issue=data["issue"],
                preferred_datetime=preferred_dt,  # 👈 Use converted string
                s3_photos=s3_photos,
            )


            # Send to SQS for async processing
            aws_utils.send_appointment_message_to_sqs(appt)

            # ✅ (1) Send confirmation to user SNS topic
            sns_client = boto3.client("sns", region_name=settings.AWS_REGION)
            user_message = (
                f"Hello {user['full_name']},\n\n"
                f"Your service appointment has been booked successfully.\n"
                f"Issue: {data['issue']}\n"
                f"Preferred Date/Time: {data['preferred_datetime']}\n\n"
                f"Our team will contact you soon.\n\n"
                f"Thank you,\nSmart Energy Services Team"
            )

            sns_client.publish(
                TopicArn=settings.SNS_USER_TOPIC_ARN,
                Subject="Appointment Confirmation",
                Message=user_message,
            )
            print("✅ User confirmation email sent via SNS")

            # ✅ (2) Use smartnotifier library for admin alert
            notifier = SmartNotifier.notify(sns_client, settings.SNS_ADMIN_TOPIC_ARN)
            result = notifier.notify(appt)
            print("✅ Admin alert sent:", result)

            messages.success(request, "Appointment booked successfully!")
            return redirect(reverse("appointments:dashboard"))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AppointmentForm()

    return render(request, "appointments/book.html", {"user": user, "form": form})

from django.shortcuts import get_object_or_404  # you may need for 404 handling

def update_appointment(request, appointment_id):
    """
    Allow user to update an appointment only if it is still pending.
    """
    user = current_user(request)
    if not user:
        return redirect(reverse("appointments:login"))

    # Fetch appointment from DynamoDB
    try:
        response = aws_utils.appointments_table.get_item(Key={"appointment_id": appointment_id})
        appointment = response.get("Item")
    except Exception as e:
        messages.error(request, f"Error fetching appointment: {e}")
        return redirect(reverse("appointments:dashboard"))

    # Permission + status check
    if not appointment or appointment["user_id"] != user["user_id"]:
        messages.error(request, "You are not allowed to edit this appointment.")
        return redirect(reverse("appointments:dashboard"))
    if appointment["status"] != "PENDING":
        messages.error(request, "You can only edit appointments that are still pending.")
        return redirect(reverse("appointments:dashboard"))

    # Pre-fill form with existing data
    if request.method == "POST":
        form = AppointmentForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            s3_photos = appointment.get("s3_photos", [])

            # If new files uploaded, append to S3
            # Handle uploaded images
            files = request.FILES.getlist("photos")

            if files:
                # ✅ Replace existing images with new uploads
                s3_photos = []
                for f in files:
                    key = aws_utils.generate_s3_key(f.name)
                    aws_utils.upload_file_to_s3(f, key, f.content_type)
                    s3_photos.append(
                        f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
                    )
            else:
                # ✅ Keep old photos if no new uploads
                s3_photos = appointment.get("s3_photos", [])

            # Update appointment in DynamoDB
            try:
                aws_utils.appointments_table.update_item(
                    Key={"appointment_id": appointment_id},
                    UpdateExpression="SET issue=:i, preferred_datetime=:d, s3_photos=:p",
                    ExpressionAttributeValues={
                        ":i": data["issue"],
                        ":d": data["preferred_datetime"],
                        ":p": s3_photos,
                    },
                )
                messages.success(request, "Appointment updated successfully!")
                return redirect(reverse("appointments:dashboard"))
            except Exception as e:
                messages.error(request, f"Error updating appointment: {e}")
    else:
        initial = {
            "issue": appointment.get("issue"),
            "preferred_datetime": appointment.get("preferred_datetime"),
        }
        form = AppointmentForm(initial=initial)

    return render(
        request,
        "appointments/update_appointment.html",
        {"form": form, "appointment": appointment, "user": user},
    )

def delete_appointment(request, appointment_id):
    """
    Show a delete confirmation page and allow the user to delete
    an appointment only if it's still pending.
    """
    user = current_user(request)
    if not user:
        return redirect(reverse("appointments:login"))

    # Get appointment from DynamoDB
    try:
        response = aws_utils.appointments_table.get_item(Key={"appointment_id": appointment_id})
        appointment = response.get("Item")
    except Exception as e:
        messages.error(request, f"Error fetching appointment: {e}")
        return redirect(reverse("appointments:dashboard"))

    # Permission & status checks
    if not appointment or appointment["user_id"] != user["user_id"]:
        messages.error(request, "You are not allowed to delete this appointment.")
        return redirect(reverse("appointments:dashboard"))

    if appointment["status"] != "PENDING":
        messages.error(request, "You can only delete appointments that are still pending.")
        return redirect(reverse("appointments:dashboard"))

    # Handle POST (actual delete confirmation)
    if request.method == "POST":
        try:
            aws_utils.appointments_table.delete_item(Key={"appointment_id": appointment_id})
            messages.success(request, "Appointment deleted successfully.")
            return redirect(reverse("appointments:dashboard"))
        except Exception as e:
            messages.error(request, f"Error deleting appointment: {e}")
            return redirect(reverse("appointments:dashboard"))

    # Handle GET (render confirmation page)
    return render(
        request,
        "appointments/delete_appointment.html",
        {"appointment": appointment, "user": user},
    )

