from django.urls import path
from . import views
from . import admin_views

app_name = "appointments"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("book/", views.book_view, name="book"),

    path("admin-dashboard/", admin_views.admin_dashboard, name="admin_dashboard"),
    path("admin-dashboard/update/<str:appointment_id>/", admin_views.update_status, name="update_status"),

    path("update/<str:appointment_id>/", views.update_appointment, name="update_appointment"),
    path("delete/<str:appointment_id>/", views.delete_appointment, name="delete_appointment"),
]
