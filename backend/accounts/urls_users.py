"""Administrator user-management API routes (mounted under /api/users/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.UserListCreateView.as_view(), name="user-list"),
    path("<int:pk>/", views.UserDetailView.as_view(), name="user-detail"),
    path("<int:pk>/reset-password/", views.UserPasswordResetView.as_view(), name="user-password-reset"),
]
