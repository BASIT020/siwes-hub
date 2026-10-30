"""
Django settings for the SIWES Hub project.

The application is a local, single-computer academic demonstration system.
It is deliberately configured to be simple, portable and safe on a normal
Windows machine, and is NOT production-hardened.
"""
import os
from pathlib import Path

# BASE_DIR is the "backend" folder. The whole project sits one level above it.
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_ROOT = PROJECT_ROOT / "frontend"

# The working SQLite database lives in a writable data directory that is
# different from the Django source tree (see section 15 of the spec).
DATA_DIR = PROJECT_ROOT / "database" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# SECURITY WARNING: keep the secret key used in production secret!
# For this academic demonstration the key is generated once into an
# environment file next to the backend folder. See core/management
# "ensure_secret_key" helper used by the launchers.
SECRET_KEY_FILE = BASE_DIR.parent / "database" / "secret_key.txt"


def _load_secret_key() -> str:
    """Load or lazily create a local development secret key."""
    try:
        value = SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
        if len(value) >= 32:
            return value
    except OSError:
        pass
    import secrets

    value = secrets.token_urlsafe(64)
    try:
        SECRET_KEY_FILE.write_text(value, encoding="utf-8")
    except OSError:
        pass  # fall back to the generated in-memory value
    return value


# Production deployments provide SIWES_SECRET_KEY in the web app's
# environment variables (kept far away from the source code). Local
# development falls back to the generated file wiped into database/.
SECRET_KEY = _load_secret_key() if not os.environ.get("SIWES_SECRET_KEY") else os.environ["SIWES_SECRET_KEY"]  # noqa: E501

# SECURITY WARNING: don't run with debug turned on in production!
# Fail-closed: production deployments set SIWES_DEBUG=0 (or leave it unset);
# the local launcher (START_APP.bat) sets SIWES_DEBUG=1 explicitly for the
# development niceties (traceback pages etc.).
DEBUG = os.environ.get("SIWES_DEBUG", "0").strip().lower() not in ("0", "false", "off", "no")


def _env_list(name: str) -> list:
    """Comma-separated environment variable, empty when unset."""
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


ALLOWED_HOSTS = _env_list("SIWES_ALLOWED_HOSTS") or ["localhost", "127.0.0.1", "testserver"]

# Session based authentication is used, so CSRF must consider the origins
# the app is actually served from. Production sets SIWES_CSRF_TRUSTED_ORIGINS
# to the deployed https origin.
CSRF_TRUSTED_ORIGINS = _env_list("SIWES_CSRF_TRUSTED_ORIGINS") or [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# --------------------------------------------------------------------------- #
# HTTPS hardening for production (PythonAnywhere terminates SSL and forwards
# the original protocol as X-Forwarded-Proto). All of this is opt-in via the
# SIWES_SECURE environment flag so local development is unchanged.
# --------------------------------------------------------------------------- #
if os.environ.get("SIWES_SECURE", "").lower() in ("1", "true", "yes"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 86400  # deliberately modest; can be raised later
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # SIWES Hub applications
    "accounts",
    "core",
    "organizations",
    "students",
    "supervisors",
    "logs",
    "reports",
    "attendance",
    "projects",
    "announcements",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_ROOT / "pages"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database - SQLite for portability (see spec section 3 and 11).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# Static assets (CSS/JS/images) are plain files in the frontend folder and
# are served by Django in development mode. STATICFILES_DIRS is used by
# collectstatic during portable packaging.
STATIC_URL = "static/"
STATICFILES_DIRS = [FRONTEND_ROOT]
STATIC_ROOT = PROJECT_ROOT / "staticfiles"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Django REST Framework configuration
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.OptionalPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_THROTTLE_RATES": {},
}

# Simple (in-memory, per-process) protection against repeated failed logins,
# used by the accounts login view. Adequate for a single-user demonstration.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 600
