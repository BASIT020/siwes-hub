"""Attendance API routes (mounted under /api/attendance/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.AttendanceListCreateView.as_view(), name="attendance-list"),
    path("summary/", views.AttendanceSummaryView.as_view(), name="attendance-summary"),
    path("<int:pk>/", views.AttendanceDetailView.as_view(), name="attendance-detail"),
]
