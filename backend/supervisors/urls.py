"""Supervisor API routes (mounted under /api/supervisors/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.SupervisorListCreateView.as_view(), name="supervisor-list"),
    path("<int:pk>/", views.SupervisorDetailView.as_view(), name="supervisor-detail"),
]
