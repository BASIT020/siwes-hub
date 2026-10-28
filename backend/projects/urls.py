"""Project API routes (mounted under /api/projects/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.MyProjectView.as_view(), name="project-me"),
    path("me/submit/", views.MyProjectSubmitView.as_view(), name="project-me-submit"),
    path("", views.ProjectListView.as_view(), name="project-list"),
    path("<int:pk>/review/", views.ProjectReviewView.as_view(), name="project-review"),
]
