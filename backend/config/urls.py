"""
Root URL router for SIWES Hub.

Responsibilities:
1. Serve the static frontend files (HTML pages, CSS, JS, assets) so that the
   whole application is reachable from one local server - no CORS and no
   separate static file server is needed.
2. Include every API endpoint under /api/.
3. Provide Django admin at /django-admin/ (kept off the obvious /admin path).
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve

from . import pages

# API routes for each application
api_urlpatterns = [
    path("auth/", include("accounts.urls")),
    path("core/", include("core.urls")),
    path("users/", include("accounts.urls_users")),
    path("organizations/", include("organizations.urls")),
    path("students/", include("students.urls")),
    path("supervisors/", include("supervisors.urls")),
    path("logs/", include("logs.urls")),
    path("reports/", include("reports.urls")),
    path("attendance/", include("attendance.urls")),
    path("projects/", include("projects.urls")),
    path("announcements/", include("announcements.urls")),
    path("notifications/", include("notifications.urls")),
]

def serve_static(request, path, document_root):
    """Static file serving with sane caching: always revalidate (no stale
    JavaScript after an update), 404 otherwise."""
    response = static_serve(request, path, document_root=document_root)
    response["Cache-Control"] = "no-cache"
    return response


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", include(api_urlpatterns)),
    # ---------------------------------------------------------------
    # Frontend static file serving (development / demonstration only).
    # django.views.static.serve uses safe_join internally, so path
    # traversal outside each documented root is rejected.
    # ---------------------------------------------------------------
    path("", pages.index),
    path("pages/<path:path>", pages.page),
    path("css/<path:path>", serve_static, {"document_root": settings.FRONTEND_ROOT / "css"}),
    path("js/<path:path>", serve_static, {"document_root": settings.FRONTEND_ROOT / "js"}),
    path(
        "assets/<path:path>",
        serve_static,
        {"document_root": settings.FRONTEND_ROOT / "assets"},
    ),
]
