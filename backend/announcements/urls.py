"""Announcement API routes (mounted under /api/announcements/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.AnnouncementListCreateView.as_view(), name="announcement-list"),
    path("<int:pk>/", views.AnnouncementDetailView.as_view(), name="announcement-detail"),
    path("<int:pk>/read/", views.AnnouncementMarkReadView.as_view(), name="announcement-read"),
]
