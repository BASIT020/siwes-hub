"""
Authentication endpoints (login, logout, who-am-i, CSRF) plus the
administrator user-management endpoints.

The frontend uses Django session authentication. To make session requests the
frontend first asks this module for a CSRF token cookie via GET /api/auth/csrf/;
every writing request then includes an X-CSRFToken header.
"""
import time
from collections import defaultdict

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import check_password
from django.db import transaction
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.middleware.csrf import get_token

from core.utils import audit
from core.pagination import paginate_response

from .models import User
from .serializers import (
    AuthUserSerializer,
    PasswordResetSerializer,
    StudentRegistrationSerializer,
    SupervisorRegistrationSerializer,
    UserSummarySerializer,
)

# In-memory failed login tracker (single-process demonstration app).
_failed_logins = defaultdict(list)


def _recent_failures(username: str) -> int:
    """Count how many logins for `username` failed inside the attempt window."""
    now = time.monotonic()
    window = settings.LOGIN_ATTEMPT_WINDOW_SECONDS
    entries = [t for t in _failed_logins.get(username.lower(), []) if now - t < window]
    _failed_logins[username.lower()] = entries
    return len(entries)


def _record_failure(username: str) -> None:
    _failed_logins[username.lower()].append(time.monotonic())


def _clear_failures(username: str) -> None:
    _failed_logins.pop(username.lower(), None)


# --------------------------------------------------------------------------- #
# Authentication views
# --------------------------------------------------------------------------- #
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def csrf(request):
    """Give the browser a CSRF token (also sets the csrftoken cookie)."""
    return Response({"csrftoken": get_token(request)})


class LoginView(APIView):
    """POST {username, password} -> starts a Django session for the user."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if _recent_failures(request.data.get("username", "")) >= settings.LOGIN_MAX_ATTEMPTS:
            return Response(
                {"detail": "Too many failed attempts. Wait ten minutes and try again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        if not username or not password:
            return Response(
                {"detail": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Students sign in with their matriculation number (which is their
        # username), but many try their email address instead. Accept both:
        # resolve an email identifier to its single account and authenticate
        # against that account's actual username. The password check itself
        # is always performed by Django's authenticate() - the same generic
        # failure message is returned for any failure, so no information
        # about which identifier matched is ever revealed.
        auth_username = username
        if "@" in username and not User.objects.filter(username__iexact=username).exists():
            by_email = User.objects.filter(email__iexact=username).first()
            if by_email is not None:
                auth_username = by_email.username

        user = authenticate(request, username=auth_username, password=password)
        if user is None:
            # Tell deactivated accounts apart, but keep the inactive account's
            # message explicit (this endpoint is username-oracle safe because
            # authentication failures always return the same generic text).
            existing = User.objects.filter(username__iexact=auth_username).first()
            if existing is not None and not existing.is_active:
                if (
                    existing.role == User.ROLE_SUPERVISOR
                    and getattr(getattr(existing, "supervisor_profile", None), "is_pending", False)
                ):
                    return Response(
                        {
                            "detail": (
                                "This supervisor account is still awaiting administrator "
                                "approval. You will be able to sign in once it is approved."
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
                return Response(
                    {"detail": "This account has been deactivated. Contact the administrator."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Always return the same generic message so attackers cannot learn
            # whether a username exists.
            _record_failure(username)
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_active:
            return Response(
                {"detail": "This account has been deactivated. Contact the administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        login(request, user)
        _clear_failures(username)
        audit(user, "LOGIN", f"User '{user.username}' signed in.")
        return Response(AuthUserSerializer(user).data)


class LogoutView(APIView):
    """POST -> end the session."""

    def post(self, request):
        logout(request)
        return Response({"detail": "Logged out."})


class MeView(APIView):
    """GET -> current user + role, used to pick the dashboard to open."""

    def get(self, request):
        return Response(AuthUserSerializer(request.user).data)


# --------------------------------------------------------------------------- #
# Public self-registration
# --------------------------------------------------------------------------- #
# Per-IP registration rate limiting (single-process demonstration app):
# slightly stricter than the login throttle, since it creates database rows.
_registration_hits = defaultdict(list)

MAX_REGISTRATIONS_PER_WINDOW = 8


def _too_many_registrations(request) -> bool:
    ip = request.META.get("REMOTE_ADDR", "") or "unknown"
    now = time.monotonic()
    window = settings.LOGIN_ATTEMPT_WINDOW_SECONDS
    entries = [t for t in _registration_hits.get(ip, []) if now - t < window]
    _registration_hits[ip] = entries
    return len(entries) >= MAX_REGISTRATIONS_PER_WINDOW


def _record_registration(request) -> None:
    ip = request.META.get("REMOTE_ADDR", "") or "unknown"
    _registration_hits[ip].append(time.monotonic())


def _notify_administrators(kind, title, body, target_url=""):
    """Notify every active administrator about a new pending account."""
    admin = None
    from notifications.utils import notify

    for user in User.objects.filter(role=User.ROLE_ADMIN, is_active=True):
        notify(user, kind, title, body, target_url)
        if admin is None:
            admin = user
    return admin


class RegisterStudentView(APIView):
    """POST /api/auth/register/student/ - create a student account + profile.

    The account is active immediately (students need no approval) and the new
    session is started at once, so the browser can send the new student to
    their dashboard.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if _too_many_registrations(request):
            return Response(
                {"detail": "Too many registration attempts. Wait ten minutes and try again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        serializer = StudentRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        _record_registration(request)
        audit(user, "STUDENT REGISTRATION", f"New student account '{user.username}' self-registered.")
        login(request, user)  # straight to the student dashboard
        return Response(AuthUserSerializer(user).data, status=status.HTTP_201_CREATED)


class RegisterSupervisorView(APIView):
    """POST /api/auth/register/supervisor/ - create a pending supervisor account.

    The account (and its profile) start inactive; an administrator approves it
    from the Supervisors page. No session is started; the API response explains
    the pending state.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if _too_many_registrations(request):
            return Response(
                {"detail": "Too many registration attempts. Wait ten minutes and try again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        serializer = SupervisorRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        _record_registration(request)
        audit(user, "SUPERVISOR REGISTRATION", f"New supervisor account '{user.username}' awaits approval.")
        _notify_administrators(
            "account",
            "Supervisor approval needed",
            f"{user.full_name} registered as a supervisor. Approve the account on the Supervisors page.",
            target_url="/pages/supervisors.html",
            )
        return Response(
            {
                "detail": (
                    "Registration received. The supervisor account is pending administrator "
                    "approval; you will be able to sign in once it is approved."
                ),
                "status": "pending_approval",
                "username": user.username,
            },
            status=status.HTTP_201_CREATED,
        )


class ChangePasswordView(APIView):
    """POST {current_password, new_password} -> user changes own password."""

    def post(self, request):
        serializer = PasswordResetSerializer(
            data={"new_password": request.data.get("new_password") or ""},
            context={"target_user": request.user},
        )
        serializer.is_valid(raise_exception=True)
        current = request.data.get("current_password") or ""
        if not check_password(current, request.user.password):
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        audit(request.user, "PASSWORD CHANGE", f"User '{request.user.username}' changed their password.")
        return Response({"detail": "Password changed."})


# --------------------------------------------------------------------------- #
# Administrator user-management endpoints (/api/users/)
# --------------------------------------------------------------------------- #
class IsAdministrator(permissions.BasePermission):
    """Only users with the Administrator role may call these views."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin_role


class UserListCreateView(generics.ListCreateAPIView):
    """GET (list/search users) and POST (create account) - administrators."""

    serializer_class = UserSummarySerializer
    permission_classes = [IsAdministrator]
    filterset_fields = ["role", "is_active"]

    def get_queryset(self):
        queryset = User.objects.all()
        search = self.request.query_params.get("search")
        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(full_name__icontains=search)
                | Q(email__icontains=search)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        data = request.data
        errors = {}
        username = (data.get("username") or "").strip()
        role = data.get("role") or ""
        password = data.get("password") or ""
        if not username:
            errors["username"] = "Username is required."
        elif User.objects.filter(username__iexact=username).exists():
            errors["username"] = "That username is already taken."
        if role not in dict(User.ROLES):
            errors["role"] = "Role must be student, supervisor or admin."
        if len(password) < 6:
            errors["password"] = "Password must be at least 6 characters."
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = User(username=username, role=role)
            user.full_name = (data.get("full_name") or "").strip()
            user.email = (data.get("email") or "").strip()
            user.phone = (data.get("phone") or "").strip()
            user.is_active = True if data.get("is_active") is None else bool(data.get("is_active"))
            user.set_password(password)
            user.save()
            # Automatically create the matching profile so dashboards work.
            if role == User.ROLE_STUDENT:
                from students.models import StudentProfile

                StudentProfile.objects.get_or_create(user=user)
            elif role == User.ROLE_SUPERVISOR:
                from supervisors.models import SupervisorProfile

                SupervisorProfile.objects.get_or_create(user=user)
        audit(request.user, "USER CREATED", f"Created {role} account '{user.username}'.")
        return Response(UserSummarySerializer(user).data, status=status.HTTP_201_CREATED)


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE a single account - administrators only.

    DELETE deactivates the account instead of removing it so that historical
    records (logs, reports, reviews...) keep their author.
    """

    queryset = User.objects.all()
    serializer_class = UserSummarySerializer
    permission_classes = [IsAdministrator]

    def update(self, request, *args, **kwargs):
        """PATCH a single account, keeping the role/profile pair consistent."""
        instance = self.get_object()
        data = request.data
        new_role = data.get("role", instance.role)
        if new_role not in dict(User.ROLES):
            return Response(
                {"role": "Invalid role."}, status=status.HTTP_400_BAD_REQUEST
            )

        from django.contrib.auth.hashers import check_password

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            serializer.save()
            if new_role == User.ROLE_STUDENT:
                from students.models import StudentProfile

                StudentProfile.objects.get_or_create(user=instance)
            elif new_role == User.ROLE_SUPERVISOR:
                from supervisors.models import SupervisorProfile

                SupervisorProfile.objects.get_or_create(user=instance)
        audit(request.user, "USER UPDATED", f"Updated account '{instance.username}'.")
        return Response(serializer.data)

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise serializers.ValidationError("You cannot deactivate your own account.")
        if instance.is_superuser:
            raise serializers.ValidationError("The superuser account cannot be deactivated.")
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        audit(self.request.user, "USER DEACTIVATED", f"Deactivated account '{instance.username}'.")
        return None


class UserPasswordResetView(generics.UpdateAPIView):
    """POST /api/users/<id>/reset-password/ - administrators set a new password."""

    queryset = User.objects.all()
    serializer_class = PasswordResetSerializer
    permission_classes = [IsAdministrator]

    def update(self, request, *args, **kwargs):
        target = self.get_object()
        serializer = self.get_serializer(
            data=request.data, context={"target_user": target}
        )
        serializer.is_valid(raise_exception=True)
        target.set_password(serializer.validated_data["new_password"])
        target.save(update_fields=["password"])
        audit(request.user, "PASSWORD RESET", f"Administrator reset the password of '{target.username}'.")
        return Response({"detail": "Password reset."})
