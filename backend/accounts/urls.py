"""Authentication-related API routes."""
from django.urls import path

from . import views

urlpatterns = [
    path("csrf/", views.csrf),
    path("login/", views.LoginView.as_view()),
    path("logout/", views.LogoutView.as_view()),
    path("me/", views.MeView.as_view()),
    path("change-password/", views.ChangePasswordView.as_view()),
    path("register/student/", views.RegisterStudentView.as_view()),
    path("register/supervisor/", views.RegisterSupervisorView.as_view()),
]
