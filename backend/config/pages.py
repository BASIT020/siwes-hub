"""
Simple, safe serving of the frontend HTML pages.

Every page lives in frontend/pages/<name>.html and is reached at
/pages/<name>.html. A fixed set of allowed page names avoids any path
traversal: unknown names return a 404 rather than touching the file system.
"""
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.views.static import serve

ALLOWED_PAGES = {
    "landing",
    "login",
    "register",
    "student-dashboard",
    "supervisor-dashboard",
    "admin-dashboard",
    "profile",
    "students",
    "supervisors",
    "organizations",
    "daily-logs",
    "weekly-reports",
    "attendance",
    "projects",
    "announcements",
    "settings",
}


def index(request):
    """Send the browser to the public landing page."""
    return redirect("pages/landing.html")


def page(request, path):
    """Serve one of the whitelisted frontend pages."""
    stem = path[:-5] if path.endswith(".html") else path
    if stem not in ALLOWED_PAGES:
        return HttpResponseNotFound("<h1>Page not found</h1>")
    return _serve_page(request, f"{stem}.html")


def _serve_page(request, file_name):
    from django.conf import settings

    response = serve(request, file_name, document_root=str(settings.FRONTEND_ROOT / "pages"))
    # Always revalidate so users never run stale HTML (with old JS wiring)
    # against a freshly deployed backend - same policy as /css/ and /js/.
    response["Cache-Control"] = "no-cache"
    return response
