"""Weekly report API routes (mounted under /api/reports/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.WeeklyReportListCreateView.as_view(), name="report-list"),
    path("<int:pk>/", views.WeeklyReportDetailView.as_view(), name="report-detail"),
    path("<int:pk>/submit/", views.WeeklyReportSubmitView.as_view(), name="report-submit"),
    path("<int:pk>/review/", views.WeeklyReportReviewView.as_view(), name="report-review"),
]
