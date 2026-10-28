"""Organization API routes (mounted under /api/organizations/)."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.OrganizationListCreateView.as_view(), name="organization-list"),
    path("<int:pk>/", views.OrganizationDetailView.as_view(), name="organization-detail"),
]
