from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.conf import settings

from .forms import RegisterForm, LoginForm, AppointmentForm
from . import aws_utils

from smartnotifier import SmartNotifier
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as django_login
from django.contrib.auth.models import User

import boto3, hashlib, datetime


from appointments.aws_utils import get_secret
secret = get_secret()

def hash_password(password: str):
    salt = "nci_salt_2025"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

def login_user(request, user_item):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect(reverse("appointments:admin_dashboard"))
    
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

def register_view(request):

    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect(reverse("appointments:admin_dashboard"))
    
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data

            if aws_utils.get_user_by_email(data["email"]):
                form.add_error("email", "Email already registered")
                return render(request, "appointments/register.html", {"form": form})

            # Saving user in DynamoDB
            password_hash = aws_utils.hash_password(data["password"])
            user_item = aws_utils.create_user(
                email=data["email"],
                password_hash=password_hash,
                full_name=data["full_name"],
            )

            sns_client = boto3.client("sns", region_name=settings.AWS_REGION)
            try:
                response = sns_client.subscribe(
                    TopicArn=settings.SNS_USER_TOPIC_ARN,
                    Protocol="email",
                    Endpoint=data["email"],
                    ReturnSubscriptionArn=False,
                )
                print(f"Subscription initiated for {data['email']}: {response}")
            except Exception as e:
                print(f"Error subscribing user to SNS: {e}")

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

    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect(reverse("appointments:admin_dashboard"))

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            try:
                if User.objects.filter(email=email).exists():

                    user_name = User.objects.get(email=email).username
                    django_user = authenticate(request, username=user_name, password=password)
                    if django_user is not None:
                        django_login(request, django_user)
                        messages.success(request, "Admin logged in successfully.")
                        return redirect(reverse("appointments:admin_dashboard"))
                    else:
                        form.add_error("password", "Incorrect admin password")
                        return render(request, "appointments/login.html", {"form": form})
            except Exception as e:
                print("Admin lookup error:", e)

            user_item = aws_utils.get_user_by_email(email)

            if not user_item:
                form.add_error("email", "User not found")
                return render(request, "appointments/login.html", {"form": form})

            if user_item["password_hash"] != aws_utils.hash_password(password):
                form.add_error("password", "Incorrect password")
                return render(request, "appointments/login.html", {"form": form})

            login_user(request, user_item)

            if user_item.get("is_admin"):
                return redirect(reverse("appointments:admin_dashboard"))

            return redirect(reverse("appointments:dashboard"))

    else:
        form = LoginForm()

    return render(request, "appointments/login.html", {"form": form})

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

def book_view(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect(reverse("appointments:admin_dashboard"))
    
    user = current_user(request)
    if not user:
        return redirect(reverse("appointments:login"))

    if request.method == "POST":
        form = AppointmentForm(request.POST, request.FILES)

        if form.is_valid():
            data = form.cleaned_data
            s3_photos = []

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

            appt = aws_utils.create_appointment(
                user_id=user["user_id"],
                user_email=user["email"],
                issue=data["issue"],
                preferred_datetime=preferred_dt,
                s3_photos=s3_photos,
            )


            # Sending to SQS
            aws_utils.send_appointment_message_to_sqs(appt)

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
            print("User confirmation email sent via SNS")


            notifier = SmartNotifier(sns_client, secret["SNS_ADMIN_TOPIC_ARN"])

            result = notifier.notify(appt)

            messages.success(request, "Appointment booked successfully!")
            return redirect(reverse("appointments:dashboard"))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AppointmentForm()

    return render(request, "appointments/book.html", {"user": user, "form": form})


def update_appointment(request, appointment_id):

    user = current_user(request)
    if not user:
        return redirect(reverse("appointments:login"))

    try:
        response = aws_utils.appointments_table.get_item(Key={"appointment_id": appointment_id})
        appointment = response.get("Item")
    except Exception as e:
        messages.error(request, f"Error fetching appointment: {e}")
        return redirect(reverse("appointments:dashboard"))

    if not appointment or appointment["user_id"] != user["user_id"]:
        messages.error(request, "You are not allowed to edit this appointment.")
        return redirect(reverse("appointments:dashboard"))
    if appointment["status"] != "PENDING":
        messages.error(request, "You can only edit appointments that are still pending.")
        return redirect(reverse("appointments:dashboard"))

    if request.method == "POST":
        form = AppointmentForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            s3_photos = appointment.get("s3_photos", [])

            files = request.FILES.getlist("photos")

            if files:
                s3_photos = []
                for f in files:
                    key = aws_utils.generate_s3_key(f.name)
                    aws_utils.upload_file_to_s3(f, key, f.content_type)
                    s3_photos.append(
                        f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
                    )
            else:
                s3_photos = appointment.get("s3_photos", [])

            preferred_dt = data["preferred_datetime"]
            if isinstance(preferred_dt, (datetime.datetime, datetime.date)):
                preferred_dt = preferred_dt.strftime("%Y-%m-%d %H:%M:%S")

            try:
                aws_utils.appointments_table.update_item(
                    Key={"appointment_id": appointment_id},
                    UpdateExpression="SET issue=:i, preferred_datetime=:d, s3_photos=:p",
                    ExpressionAttributeValues={
                        ":i": data["issue"],
                        ":d": preferred_dt,
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
   
    user = current_user(request)
    if not user:
        return redirect(reverse("appointments:login"))

    try:
        response = aws_utils.appointments_table.get_item(Key={"appointment_id": appointment_id})
        appointment = response.get("Item")
    except Exception as e:
        messages.error(request, f"Error fetching appointment: {e}")
        return redirect(reverse("appointments:dashboard"))

    if not appointment or appointment["user_id"] != user["user_id"]:
        messages.error(request, "You are not allowed to delete this appointment.")
        return redirect(reverse("appointments:dashboard"))

    if appointment["status"] != "PENDING":
        messages.error(request, "You can only delete appointments that are still pending.")
        return redirect(reverse("appointments:dashboard"))

    if request.method == "POST":
        try:
            aws_utils.appointments_table.delete_item(Key={"appointment_id": appointment_id})
            messages.success(request, "Appointment deleted successfully.")
            return redirect(reverse("appointments:dashboard"))
        except Exception as e:
            messages.error(request, f"Error deleting appointment: {e}")
            return redirect(reverse("appointments:dashboard"))

    return render(
        request,
        "appointments/delete_appointment.html",
        {"appointment": appointment, "user": user},
    )

