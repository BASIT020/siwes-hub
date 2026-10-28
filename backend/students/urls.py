"""Student API routes (mounted under /api/students/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.StudentListCreateView.as_view(), name="student-list"),
    path("me/", views.MyStudentProfileView.as_view(), name="student-profile"),
    path("<int:pk>/", views.StudentDetailView.as_view(), name="student-detail"),
    path("skills/", views.SkillListCreateView.as_view(), name="skill-list"),
    path("skills/<int:pk>/", views.SkillDetailView.as_view(), name="skill-detail"),
]
