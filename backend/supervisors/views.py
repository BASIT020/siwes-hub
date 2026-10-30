"""
Supervisor views.

GET /api/supervisors/       - admin sees all, students see their assigned supervisor
GET/PATCH /api/supervisors/<id>/ - administrator management
"""
import json  # noqa: F401 (kept for readability of documentation examples)

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate_response
from core.utils import audit

from .models import SupervisorProfile
from .serializers import SupervisorProfileSerializer

User = get_user_model()


class SupervisorListCreateView(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Login required."}, status=status.HTTP_401_UNAUTHORIZED)
        queryset = SupervisorProfile.objects.select_related("user").all()
        if request.user.is_student_role:
            # A student may only see the supervisor assigned to them (plus enough
            # public details). Everything else is filtered server-side.
            placement = getattr(request.user.student_profile, "placement", None)
            if placement and placement.supervisor:
                queryset = SupervisorProfile.objects.filter(pk=placement.supervisor_id)
            else:
                queryset = SupervisorProfile.objects.none()
        elif not (request.user.is_admin_role or request.user.is_supervisor_role):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        search = request.query_params.get("search")
        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(user__full_name__icontains=search)
                | Q(user__username__icontains=search)
                | Q(department__icontains=search)
            )
        # Administrator helper for the "Pending supervisor approvals" section.
        if request.query_params.get("pending") == "true":
            if not request.user.is_admin_role:
                return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
            queryset = queryset.filter(is_pending=True)
        return paginate_response(SupervisorProfileSerializer, request, queryset)

    def post(self, request):
        """Administrator registers a supervisor (user account + profile)."""
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can register supervisors."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        errors = {}
        username = (data.get("username") or "").strip()
        full_name = (data.get("full_name") or "").strip()
        password = data.get("password") or ""
        if not username:
            errors["username"] = "Username is required."
        elif User.objects.filter(username__iexact=username).exists():
            errors["username"] = "That username is already taken."
        if not full_name:
            errors["full_name"] = "Full name is required."
        email = (data.get("email") or "").strip()
        if email and User.objects.filter(email__iexact=email).exists():
            errors["email"] = "That email address is already registered."
        try:
            validate_password(password)
        except DjangoValidationError as exc:
            errors["password"] = " ".join(part for part in exc.messages if isinstance(part, str))
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = User(
                username=username,
                role=User.ROLE_SUPERVISOR,
                full_name=full_name,
                email=email,
                phone=(data.get("phone") or "").strip(),
            )
            user.set_password(password)
            user.save()
            profile = SupervisorProfile(
                user=user,
                staff_id=(data.get("staff_id") or "").strip(),
                title=(data.get("title") or "").strip(),
                department=(data.get("department") or "").strip(),
            )
            profile.save()
        audit(request.user, "SUPERVISOR CREATED", f"Registered supervisor '{full_name}'.")
        return Response(SupervisorProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class SupervisorDetailView(APIView):
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return Response({"detail": "Login required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            profile = SupervisorProfile.objects.select_related("user").get(pk=pk)
        except SupervisorProfile.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if request.user.is_student_role:
            placement = getattr(request.user.student_profile, "placement", None)
            if not (placement and placement.supervisor_id == profile.pk):
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        elif not (request.user.is_admin_role or request.user.is_supervisor_role):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        return Response(SupervisorProfileSerializer(profile).data)

    def patch(self, request, pk):
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can edit supervisors."}, status=status.HTTP_403_FORBIDDEN)
        try:
            profile = SupervisorProfile.objects.get(pk=pk)
        except SupervisorProfile.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SupervisorProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user_data = serializer.validated_data.pop("user", {}) if "user" in serializer.validated_data else {}
        with transaction.atomic():
            was_active = profile.is_active
            user_was_active = profile.user.is_active
            was_pending = profile.is_pending
            instance = serializer.save()
            user = instance.user
            for field in ("full_name", "email", "phone"):
                if field in user_data:
                    setattr(user, field, user_data[field])
            # Whenever the administrator changes the profile's active state,
            # the paired user account is kept in the same state. Activating a
            # pending/self-registered supervisor here is exactly how the
            # administrator approves the account.
            activating = "is_active" in serializer.validated_data
            if activating:
                user.is_active = instance.is_active
                if instance.is_active:
                    instance.is_pending = False
                else:
                    instance.is_pending = False  # rejected/closed, not pending anymore
            user.save()
            if activating:
                instance.save(update_fields=["is_pending"])
        if activating and not was_active and instance.is_active:
            audit(
                request.user,
                "SUPERVISOR APPROVED" if was_pending else "SUPERVISOR ACTIVATED",
                f"{'Approved' if was_pending else 'Activated'} supervisor '{instance}'.",
            )
            from notifications.utils import notify

            notify(
                user,
                "account",
                "Account approved",
                "Your supervisor account was approved. You can now sign in with your username and password.",
            )
        elif activating and not instance.is_active and not was_active and was_pending:
            # An administrator declined a self-registered supervisor account.
            # The user account stays inactive (it can never sign in) and the
            # pending flag is cleared, so the registration leaves the queue.
            audit(request.user, "SUPERVISOR REJECTED", f"Rejected supervisor registration '{instance}'.")
            from notifications.utils import notify

            notify(
                user,
                "account",
                "Registration declined",
                "Your supervisor registration was reviewed and not approved. "
                "Please contact the SIWES office if you believe this is an error.",
            )
        elif activating and was_active and not instance.is_active:
            if user_was_active:
                audit(request.user, "SUPERVISOR DEACTIVATED", f"Deactivated supervisor '{instance}'.")
        else:
            audit(request.user, "SUPERVISOR UPDATED", f"Updated supervisor '{instance}'.")
        return Response(SupervisorProfileSerializer(instance).data)
