"""
Daily log API views.

Endpoints (mounted under /api/logs/):
* GET    /                list (role-filtered; ?status=&student=&date_from=&date_to=)
* POST   /                create a draft (students)
* GET    /<id>/           detail (owner, assigned supervisor, admin)
* PATCH  /<id>/           edit draft/rejected (owner)
* DELETE /<id>/           delete a draft (owner)
* POST   /<id>/submit/    draft/rejected -> submitted (owner)
* POST   /<id>/review/    submitted -> approved/rejected + comment (assigned supervisor)

Notifications and audit records are written for every state change.
"""
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate_response
from core.utils import audit, get_supervisor_students
from notifications.utils import notify

from .models import DailyLog
from .serializers import DailyLogSerializer, LogReviewSerializer


def _own_students(user):
    return get_supervisor_students(user.supervisor_profile)


class DailyLogListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _visible_logs(self, request):
        user = request.user
        if user.is_student_role:
            queryset = DailyLog.objects.filter(student=user.student_profile)
        elif user.is_supervisor_role:
            queryset = DailyLog.objects.filter(student__in=_own_students(user))
        elif user.is_admin_role:
            queryset = DailyLog.objects.all()
        else:
            queryset = DailyLog.objects.none()

        params = request.query_params
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("student"):
            queryset = queryset.filter(student_id=params["student"])
        if params.get("date_from"):
            queryset = queryset.filter(log_date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(log_date__lte=params["date_to"])
        search = params.get("search")
        if search:
            queryset = queryset.filter(
                Q(activities__icontains=search) | Q(tools_used__icontains=search)
            )
        return queryset.select_related("student__user").order_by("-log_date")

    def get(self, request):
        return paginate_response(DailyLogSerializer, request, self._visible_logs(request))

    def post(self, request):
        if not request.user.is_student_role:
            return Response(
                {"detail": "Only students can create daily logs."},
                status=status.HTTP_403_FORBIDDEN,
            )
        payload = dict(request.data)
        payload["student"] = request.user.student_profile.pk

        # Duplicate date check with a friendly message (the DB constraint
        # remains as the authoritative guarantee).
        existing = DailyLog.objects.filter(
            student=request.user.student_profile,
            log_date=payload.get("log_date") or timezone.localdate(),
        )
        if existing.exists():
            return Response(
                {"log_date": "You already have a log for that date. Use edit instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DailyLogSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save(
            student=request.user.student_profile,
            status=DailyLog.STATUS_DRAFT,
        )
        return Response(DailyLogSerializer(entry).data, status=status.HTTP_201_CREATED)


class DailyLogDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_visible(self, request, pk):
        try:
            entry = DailyLog.objects.select_related("student__user").get(pk=pk)
        except (DailyLog.DoesNotExist, ValueError):
            return None
        user = request.user
        if user.is_admin_role:
            return entry
        if user.is_student_role and entry.student_id == user.student_profile.id:
            return entry
        if (
            user.is_supervisor_role
            and entry.student in _own_students(user)
        ):
            return entry
        return None

    def get(self, request, pk):
        entry = self._get_visible(request, pk)
        if entry is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DailyLogSerializer(entry).data)

    def patch(self, request, pk):
        entry = self._get_visible(request, pk)
        if entry is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not (request.user.is_student_role and entry.student_id == request.user.student_profile.id):
            return Response({"detail": "Only the student who owns this log can edit it."}, status=status.HTTP_403_FORBIDDEN)
        if not entry.is_editable:
            return Response(
                {
                    "detail": "This log has been {} and can no longer be edited.".format(
                        entry.get_status_display().lower()
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload = dict(request.data)
        payload["student"] = entry.student_id
        serializer = DailyLogSerializer(entry, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        audit(
            request.user,
            "LOG EDITED",
            f"Student '{request.user.username}' edited daily log #{entry.id} "
            f"({entry.log_date}) while status was '{entry.get_status_display().lower()}'.",
        )
        return Response(DailyLogSerializer(instance).data)

    def delete(self, request, pk):
        entry = self._get_visible(request, pk)
        if entry is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not (request.user.is_student_role and entry.student_id == request.user.student_profile.id):
            return Response({"detail": "Only the owner can delete this log."}, status=status.HTTP_403_FORBIDDEN)
        if not entry.is_editable:
            return Response({"detail": "Only drafts can be deleted."}, status=status.HTTP_400_BAD_REQUEST)
        log_id = entry.id
        log_date = entry.log_date
        entry.delete()
        audit(
            request.user,
            "LOG DELETED",
            f"Student '{request.user.username}' deleted daily log #{log_id} ({log_date}).",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class DailyLogSubmitView(APIView):
    """POST /api/logs/<id>/submit/ - send a draft (or previously rejected) log for review."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_student_role:
            return Response({"detail": "Only students can submit logs."}, status=status.HTTP_403_FORBIDDEN)
        try:
            entry = DailyLog.objects.get(pk=pk, student=request.user.student_profile)
        except (DailyLog.DoesNotExist, ValueError):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if entry.status not in (DailyLog.STATUS_DRAFT, DailyLog.STATUS_REJECTED):
            return Response(
                {"detail": "This log has already been submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entry.status = DailyLog.STATUS_SUBMITTED
        entry.submitted_at = timezone.now()
        entry.save(update_fields=["status", "submitted_at", "updated_at"])
        audit(request.user, "LOG SUBMITTED", f"Daily log #{entry.id} for {entry.log_date} submitted for review.")
        notify_supervisor_of_submission(request.user.student_profile, entry)
        return Response(DailyLogSerializer(entry).data)


def notify_supervisor_of_submission(student, entry):
    """Inform the assigned supervisor that a log is waiting for review."""
    placement = getattr(student, "placement", None)
    if placement and placement.supervisor:
        notify(
            recipient=placement.supervisor.user,
            kind="log_submitted",
            title="New daily log submitted",
            body=(
                f"{student} submitted a daily log for {entry.log_date}. "
                "Open the review page to approve or reject it."
            ),
            target_url=f"pages/daily-logs.html?mode=review&id={entry.id}",
        )


def notify_student_of_review(entry, decision):
    """Inform the student about an approval/rejection of their log."""
    title = "Daily log approved" if decision == "approve" else "Daily log rejected"
    body = (
        f"Your daily log for {entry.log_date} was {entry.status}."
        + (f' Supervisor comment: "{entry.supervisor_comment}"' if entry.supervisor_comment else "")
    )
    notify(
        recipient=entry.student.user,
        kind="log_reviewed",
        title=title,
        body=body,
        target_url=f"pages/daily-logs.html?id={entry.id}",
    )


class DailyLogReviewView(APIView):
    """POST /api/logs/<id>/review/ - the assigned supervisor approves or rejects."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_supervisor_role:
            return Response({"detail": "Only supervisors can review daily logs."}, status=status.HTTP_403_FORBIDDEN)
        try:
            entry = DailyLog.objects.select_related("student__user").get(pk=pk)
        except (DailyLog.DoesNotExist, ValueError):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not entry.can_be_reviewed_by(request.user.supervisor_profile):
            return Response(
                {"detail": "This log is not assigned to you, or it is not awaiting review."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = LogReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        comment = serializer.validated_data.get("comment", "")
        if decision == "reject" and not comment.strip():
            return Response(
                {"comment": "A reason is required when rejecting a log."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry.status = (
            DailyLog.STATUS_APPROVED if decision == "approve" else DailyLog.STATUS_REJECTED
        )
        entry.supervisor = request.user.supervisor_profile
        entry.supervisor_comment = comment
        entry.reviewed_at = timezone.now()
        entry.save(
            update_fields=[
                "status", "supervisor", "supervisor_comment", "reviewed_at", "updated_at"
            ]
        )
        audit(
            request.user,
            "LOG REVIEWED",
            f"Daily log #{entry.id} ({entry.log_date}) of '{entry.student}' -> {entry.status}.",
        )
        notify_student_of_review(entry, decision)
        return Response(DailyLogSerializer(entry).data)
