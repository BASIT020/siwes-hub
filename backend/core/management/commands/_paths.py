"""Single source of truth for the demo credentials file location."""
from django.conf import settings


def credentials_path():
    """The database/demo_credentials.txt file (never part of version control)."""
    return settings.PROJECT_ROOT / "database" / "demo_credentials.txt"
