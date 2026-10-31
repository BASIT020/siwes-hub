"""Supervisor API routes (mounted under /api/supervisors/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.SupervisorListCreateView.as_view(), name="supervisor-list"),
    path("<int:pk>/", views.SupervisorDetailView.as_view(), name="supervisor-detail"),
    path("<int:pk>/approve/", views.SupervisorApproveView.as_view(), name="supervisor-approve"),
    path("<int:pk>/reject/", views.SupervisorRejectView.as_view(), name="supervisor-reject"),
]
