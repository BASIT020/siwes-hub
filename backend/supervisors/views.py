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
from django.db.models import Q
from django.utils import timezone
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
        # Status filter for the approval queue (admins only).
        status_filter = {
            "pending": Q(is_pending=True),
            "approved": Q(is_active=True, is_pending=False, rejected_at__isnull=True),
            "rejected": Q(is_active=False, rejected_at__isnull=False),
            "inactive": Q(is_active=False, rejected_at__isnull=True),
        }
        state = request.query_params.get("status")
        if state:
            if not request.user.is_admin_role:
                return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
            if state not in status_filter:
                return Response(
                    {"detail": "status must be pending, approved, rejected or inactive."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(status_filter[state])
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
        return Response(
            SupervisorProfileSerializer(profile, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


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
        return Response(SupervisorProfileSerializer(profile, context={"request": request}).data)

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
            was_rejected = profile.rejected_at is not None
            instance = serializer.save()
            user = instance.user
            for field in ("full_name", "email", "phone"):
                if field in user_data:
                    setattr(user, field, user_data[field])
            # Whenever the administrator changes the profile's active state,
            # the paired user account is kept in the same state. Activating a
            # pending/self-registered supervisor here approves the account.
            activating = "is_active" in serializer.validated_data
            if activating:
                user.is_active = instance.is_active
                if instance.is_active:
                    instance.is_pending = False
                    # (Re-)granting access: stamp the approver and wipe any
                    # earlier rejection paperwork.
                    instance.approved_by = request.user
                    instance.approved_at = timezone.now()
                    instance.rejected_by = None
                    instance.rejected_at = None
                    instance.rejected_reason = ""
                else:
                    instance.is_pending = False  # rejected/closed, not pending anymore
                    if was_pending:
                        instance.rejected_by = request.user
                        instance.rejected_at = timezone.now()
                        instance.rejected_reason = (request.data.get("rejected_reason") or "").strip()
            user.save()
            if activating:
                instance.save(
                    update_fields=[
                        "is_pending", "approved_by", "approved_at",
                        "rejected_by", "rejected_at", "rejected_reason",
                    ]
                )
        if activating and not was_active and instance.is_active:
            if was_pending or was_rejected:
                action = "SUPERVISOR APPROVED" if was_pending else "SUPERVISOR REACTIVATED"
                verb = "Approved" if was_pending else "Reactivated"
            else:
                action = "SUPERVISOR ACTIVATED"
                verb = "Activated"
            audit(request.user, action, f"{verb} supervisor '{instance}'.")
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
            reason = instance.rejected_reason or "(no reason given)"
            audit(
                request.user,
                "SUPERVISOR REJECTED",
                f"Rejected supervisor registration '{instance}'. Reason: {reason}",
            )
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
        return Response(SupervisorProfileSerializer(instance, context={"request": request}).data)


class SupervisorApproveView(APIView):
    """POST /api/supervisors/<id>/approve/ - administrators only.

    Grants (or re-grants) sign-in access: activates the paired user account,
    stamps the approving administrator and the decision time, and wipes any
    earlier rejection paperwork. Duplicate approve/activate calls are rejected
    with a clear 400 instead of silently re-stamping."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can approve supervisors."}, status=status.HTTP_403_FORBIDDEN)
        try:
            profile = SupervisorProfile.objects.select_related("user").get(pk=pk)
        except SupervisorProfile.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if profile.is_active and not profile.is_pending:
            return Response(
                {"detail": "This supervisor is already approved and active."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        was_pending = profile.is_pending
        was_rejected = profile.rejected_at is not None
        with transaction.atomic():
            user = profile.user
            user.is_active = True
            user.save(update_fields=["is_active"])
            profile.is_active = True
            profile.is_pending = False
            profile.approved_by = request.user
            profile.approved_at = timezone.now()
            profile.rejected_by = None
            profile.rejected_at = None
            profile.rejected_reason = ""
            profile.save(update_fields=[
                "is_active", "is_pending", "approved_by", "approved_at",
                "rejected_by", "rejected_at", "rejected_reason",
            ])
        if was_pending or was_rejected:
            action = "SUPERVISOR APPROVED" if was_pending else "SUPERVISOR REACTIVATED"
            verb = "Approved" if was_pending else "Reactivated"
        else:
            action = "SUPERVISOR ACTIVATED"
            verb = "Activated"
        audit(request.user, action, f"{verb} supervisor '{profile}'.")
        from notifications.utils import notify

        notify(
            profile.user,
            "account",
            "Account approved",
            "Your supervisor account was approved. You can now sign in with your username and password.",
        )
        return Response(
            SupervisorProfileSerializer(profile, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class SupervisorRejectView(APIView):
    """POST /api/supervisors/<id>/reject/ - administrators only, reason required.

    Declines a pending self-registered supervisor: the account stays inactive
    (never able to sign in), the reason plus the deciding administrator and
    decision time are stored, and the applicant is notified. Nothing is
    deleted - a rejected registration can still be reviewed/reactivated."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can reject supervisors."}, status=status.HTTP_403_FORBIDDEN)
        try:
            profile = SupervisorProfile.objects.select_related("user").get(pk=pk)
        except SupervisorProfile.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not profile.is_pending:
            return Response(
                {"detail": "Only pending supervisor registrations can be rejected. "
                           "Use the deactivate action for approved supervisors."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"reason": "A rejection reason is required."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            user = profile.user
            user.is_active = False
            user.save(update_fields=["is_active"])
            profile.is_active = False
            profile.is_pending = False
            profile.rejected_by = request.user
            profile.rejected_at = timezone.now()
            profile.rejected_reason = reason
            profile.save(update_fields=[
                "is_active", "is_pending", "rejected_by", "rejected_at", "rejected_reason",
            ])
        audit(
            request.user,
            "SUPERVISOR REJECTED",
            f"Rejected supervisor registration '{profile}'. Reason: {reason}",
        )
        from notifications.utils import notify

        notify(
            user,
            "account",
            "Registration declined",
            "Your supervisor registration was reviewed and not approved. "
            "Please contact the SIWES office if you believe this is an error.",
        )
        return Response(
            SupervisorProfileSerializer(profile, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
