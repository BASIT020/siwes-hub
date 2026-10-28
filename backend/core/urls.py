"""Core application API routes (mounted under /api/core/)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from . import views as core_views

router = DefaultRouter()
router.register("sessions", core_views.SIWESSessionViewSet, basename="session")
router.register("placements", core_views.PlacementViewSet, basename="placement")

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("", include(router.urls)),
]
