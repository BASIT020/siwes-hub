"""
Create the first administrator account - the secure replacement for seeded
demo accounts.

Interaction rules:

* If any administrator account already exists the command does nothing
  (exit code 0), so it is always safe to call during startup.
* Otherwise it asks for username, email and password. The password is read
  with hidden input (getpass), never echoed, never written to a file, and
  validated against Django's password validators.
* The account is created with the Administrator role and a password hash
  (set_password), exactly like a real production superuser.
* For non-interactive automation use --username/--email and either answer the
  password prompt or pass --password-for-tests (development/testing only).

    python manage.py bootstrap_admin
    python manage.py bootstrap_admin --username siwes.office --email office@school.edu
"""
import getpass
import re

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from core.utils import record_audit_log

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Command(BaseCommand):
    help = (
        "Create the first administrator account if none exists (interactive; "
        "password is typed in hidden, never printed or stored in plain text)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", default=None, help="Administrator username.")
        parser.add_argument("--email", default=None, help="Administrator email address.")
        parser.add_argument(
            "--password-for-tests",
            default=None,
            help="Password for automated tests only. NEVER use on a real database.",
        )

    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        admins = User.objects.filter(role=User.ROLE_ADMIN)
        if admins.exists():
            self.stdout.write(self.style.SUCCESS(
                "An administrator account already exists - no action needed."
            ))
            return

        username = options["username"]
        email = options["email"]
        test_password = options["password_for_tests"]

        # --------------------------------------------------------------
        # Collect credentials (hidden when interactive). If the console
        # cannot provide input (closed/redirected), explain instead of
        # crashing so the launcher can continue or restart gracefully.
        # --------------------------------------------------------------
        def _ask(label: str) -> str:
            try:
                return input(label).strip()
            except (EOFError, KeyboardInterrupt):
                raise CommandError(
                    "No interactive input available, so no administrator was created. "
                    "Start the app in a normal console window and answer the prompts, "
                    "or run: python manage.py bootstrap_admin --username <name> "
                    "--email <email>"
                )

        while not username:
            username = _ask("Administrator username: ")
        while not email:
            email = _ask("Administrator email: ")
            if email and not EMAIL_RE.match(email):
                self.stderr.write("That does not look like a valid email address.")
                email = None

        if test_password:
            password = test_password
        else:
            try:
                password = getpass.getpass("Password (typing is hidden): ")
                if len(password) < 6:
                    raise CommandError("Password must be at least 6 characters.")
                confirm = getpass.getpass("Password (again): ")
            except (EOFError, KeyboardInterrupt):
                raise CommandError(
                    "No interactive input available, so no administrator was created. "
                    "Start the app in a normal console window and answer the prompts, "
                    "or run: python manage.py bootstrap_admin --username <name> "
                    "--email <email>"
                )
            if password != confirm:
                raise CommandError("The two passwords did not match.")
            if not password:
                raise CommandError("Password is required.")

        user = User(username=username, role=User.ROLE_ADMIN, full_name="", email=email, is_active=True)
        try:
            validate_password(password, user=user)
        except Exception as exc:
            raise CommandError(f"Password rejected: {exc}") from exc
        user.set_password(password)  # salts + hashes; plain text is discarded
        user.save()
        record_audit_log(user, "ADMIN BOOTSTRAP", f"First administrator account '{user.username}' created.")
        self.stdout.write(self.style.SUCCESS(
            f"Administrator '{user.username}' created. Sign in at /pages/login.html."
        ))
