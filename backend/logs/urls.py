"""Daily log API routes (mounted under /api/logs/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.DailyLogListCreateView.as_view(), name="log-list"),
    path("<int:pk>/", views.DailyLogDetailView.as_view(), name="log-detail"),
    path("<int:pk>/submit/", views.DailyLogSubmitView.as_view(), name="log-submit"),
    path("<int:pk>/review/", views.DailyLogReviewView.as_view(), name="log-review"),
]
