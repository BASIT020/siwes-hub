"""
Views for the core application:

* DashboardView          - role-based statistics for the three dashboards
* SIWESSessionViewSet    - SIWES training session management
* PlacementViewSet       - student placement (organization/supervisor) management
* AuditLogListView       - audit trail (administrators)
"""
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from announcements.models import Announcement
from attendance.models import Attendance
from logs.models import DailyLog
from notifications.models import Notification
from organizations.models import Organization
from projects.models import StudentProject
from reports.models import WeeklyReport
from students.models import Skill, StudentProfile
from supervisors.models import SupervisorProfile

from .models import AuditLog, Placement, SIWESSession
from .serializers import AuditLogSerializer, PlacementSerializer, SIWESSessionSerializer
from .utils import audit, get_active_placement


def _attendance_summary(student_profile):
    qs = Attendance.objects.filter(student=student_profile)
    total = qs.count()
    present = qs.filter(status=Attendance.STATUS_PRESENT).count()
    rate = round((present / total) * 100) if total else 0
    return {"total_days": total, "present_days": present, "attendance_rate": rate}


class DashboardView(APIView):
    """GET /api/core/dashboard/ - stats payload for the caller's role."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_student_role:
            return _student_dashboard(user)
        if user.is_supervisor_role:
            return _supervisor_dashboard(user)
        if user.is_admin_role:
            return _admin_dashboard(user)
        return Response({"detail": "Unknown role."}, status=400)


# --------------------------------------------------------------------------- #
# Student dashboard
# --------------------------------------------------------------------------- #
def _student_dashboard(user):
    profile = user.student_profile

    logs = DailyLog.objects.filter(student=profile)
    reports = WeeklyReport.objects.filter(student=profile)
    skills = Skill.objects.filter(student=profile)

    placement = get_active_placement(profile)
    placement_data = PlacementSerializer(placement).data if placement else None

    project = StudentProject.objects.filter(student=profile).first()
    project_data = None
    if project:
        project_data = {
            "id": project.id,
            "title": project.title,
            "status": project.status,
            "review_status": project.review_status,
            "supervisor_comment": project.supervisor_comment,
        }

    # Most recent supervisor feedback (approvals, rejections, comments).
    feedback = []
    for log in logs.exclude(status=DailyLog.STATUS_DRAFT).order_by("-reviewed_at")[:5]:
        if log.status in (DailyLog.STATUS_APPROVED, DailyLog.STATUS_REJECTED) or log.supervisor_comment:
            feedback.append(
                {
                    "source": "daily log",
                    "record_id": log.id,
                    "date": log.log_date,
                    "status": log.status,
                    "comment": log.supervisor_comment,
                }
            )
    for report in reports.exclude(status=WeeklyReport.STATUS_DRAFT).order_by("-reviewed_at")[:5]:
        if report.status in (
            WeeklyReport.STATUS_APPROVED,
            WeeklyReport.STATUS_REJECTED,
        ) or report.supervisor_comment:
            feedback.append(
                {
                    "source": "weekly report",
                    "record_id": report.id,
                    "date": report.week_start,
                    "status": report.status,
                    "comment": report.supervisor_comment,
                }
            )
    feedback.sort(key=lambda f: str(f["date"]), reverse=True)
    feedback = feedback[:5]

    announcements = Announcement.visible_for(user)[:3]

    return Response(
        {
            "role": "student",
            "profile": {
                "full_name": user.full_name or user.username,
                "matric_number": profile.matric_number,
                "department": profile.department,
                "faculty": profile.faculty,
                "level": profile.level,
                "email": user.email,
                "phone": user.phone,
            },
            "placement": placement_data,
            "stats": {
                "total_logs": logs.count(),
                "draft_logs": logs.filter(status=DailyLog.STATUS_DRAFT).count(),
                "pending_logs": logs.filter(status=DailyLog.STATUS_SUBMITTED).count(),
                "approved_logs": logs.filter(status=DailyLog.STATUS_APPROVED).count(),
                "rejected_logs": logs.filter(status=DailyLog.STATUS_REJECTED).count(),
                "total_reports": reports.count(),
                "pending_reports": reports.filter(status=WeeklyReport.STATUS_SUBMITTED).count(),
                "skills_count": skills.count(),
                "attendance": _attendance_summary(profile),
            },
            "project": project_data,
            "recent_feedback": feedback,
            "announcements": [
                {
                    "id": a.id,
                    "title": a.title,
                    "content": a.content,
                    "created_at": a.created_at,
                }
                for a in announcements
            ],
            "unread_notifications": Notification.objects.filter(recipient=user, is_read=False).count(),
        }
    )


# --------------------------------------------------------------------------- #
# Supervisor dashboard
# --------------------------------------------------------------------------- #
def _supervisor_students(user):
    supervisor = user.supervisor_profile
    return StudentProfile.objects.filter(
        placement__is_active=True, placement__supervisor=supervisor
    )


def _supervisor_dashboard(user):
    students = _supervisor_students(user)
    logs = DailyLog.objects.filter(student__in=students)
    reports = WeeklyReport.objects.filter(student__in=students)
    projects = StudentProject.objects.filter(student__in=students)

    assigned = []
    for student in students:
        att = _attendance_summary(student)
        pending_logs = DailyLog.objects.filter(student=student, status=DailyLog.STATUS_SUBMITTED).count()
        assigned.append(
            {
                "id": student.id,
                "full_name": student.user.full_name or student.user.username,
                "matric_number": student.matric_number,
                "department": student.department,
                "organization": (
                    student.placement.organization.name
                    if student.placement and student.placement.organization
                    else None
                ),
                "pending_logs": pending_logs,
                "approved_logs": DailyLog.objects.filter(student=student, status=DailyLog.STATUS_APPROVED).count(),
                "attendance_rate": att["attendance_rate"],
                "needs_attention": pending_logs > 0 or DailyLog.objects.filter(student=student).count() == 0,
            }
        )
    assigned.sort(key=lambda s: (not s["needs_attention"], s["full_name"]))

    recent_reviews = []
    for log in logs.exclude(status=DailyLog.STATUS_DRAFT).exclude(status=DailyLog.STATUS_SUBMITTED).exclude(reviewed_at=None).order_by("-reviewed_at")[:8]:
        recent_reviews.append(
            {
                "kind": "Daily log",
                "record_id": log.id,
                "student": str(log.student),
                "status": log.status,
                "reviewed_at": log.reviewed_at,
                "comment": log.supervisor_comment,
            }
        )
    for report in reports.exclude(status=WeeklyReport.STATUS_DRAFT).exclude(status=WeeklyReport.STATUS_SUBMITTED).exclude(reviewed_at=None).order_by("-reviewed_at")[:8]:
        recent_reviews.append(
            {
                "kind": "Weekly report",
                "record_id": report.id,
                "student": str(report.student),
                "status": report.status,
                "reviewed_at": report.reviewed_at,
                "comment": report.supervisor_comment,
            }
        )
    recent_reviews.sort(key=lambda r: r["reviewed_at"], reverse=True)
    recent_reviews = recent_reviews[:8]

    return Response(
        {
            "role": "supervisor",
            "supervisor": {
                "full_name": user.full_name or user.username,
                "title": user.supervisor_profile.title,
                "department": user.supervisor_profile.department,
            },
            "stats": {
                "assigned_students": students.count(),
                "pending_logs": logs.filter(status=DailyLog.STATUS_SUBMITTED).count(),
                "pending_reports": reports.filter(status=WeeklyReport.STATUS_SUBMITTED).count(),
                "pending_projects": projects.filter(review_status=StudentProject.REVIEW_SUBMITTED).count(),
                "approved_logs": logs.filter(status=DailyLog.STATUS_APPROVED).count(),
            },
            "students_needing_attention": [s for s in assigned if s["needs_attention"] and s["pending_logs"] == 0],
            "assigned_students": assigned,
            "recent_reviews": recent_reviews,
        }
    )


# --------------------------------------------------------------------------- #
# Administrator dashboard
# --------------------------------------------------------------------------- #
def _admin_dashboard(user):
    placements = Placement.objects.filter(is_active=True)
    today = timezone.localdate()

    active_session = SIWESSession.objects.filter(is_active=True).order_by("-start_date").first()

    return Response(
        {
            "role": "admin",
            "stats": {
                "total_students": StudentProfile.objects.count(),
                "total_supervisors": SupervisorProfile.objects.filter(is_active=True).count(),
                "pending_supervisors": SupervisorProfile.objects.filter(is_pending=True).count(),
                "total_organizations": Organization.objects.count(),
                "active_placements": placements.count(),
                "submitted_logs": DailyLog.objects.filter(status=DailyLog.STATUS_SUBMITTED).count(),
                "approved_logs": DailyLog.objects.filter(status=DailyLog.STATUS_APPROVED).count(),
                "pending_reports": WeeklyReport.objects.filter(status=WeeklyReport.STATUS_SUBMITTED).count(),
                "pending_projects": StudentProject.objects.filter(review_status=StudentProject.REVIEW_SUBMITTED).count(),
                "students_present_today": Attendance.objects.filter(
                    status=Attendance.STATUS_PRESENT, date=today
                ).values("student").distinct().count(),
            },
            "active_session": {
                "id": active_session.id,
                "name": active_session.name,
                "start_date": active_session.start_date,
                "end_date": active_session.end_date,
            }
            if active_session
            else None,
            "organization_distribution": [
                {
                    "organization": row["organization__name"] or "Unassigned",
                    "students": row["students"],
                }
                for row in placements.values("organization__name")
                .annotate(students=Count("id"))
                .order_by("-students")[:5]
            ],
            "recent_activity": AuditLogSerializer(AuditLog.objects.all()[:10], many=True).data,
        }
    )


class IsAdministratorOrReadOnly(IsAuthenticated):
    """Create/update/delete for administrators; every authenticated user may read."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_admin_role


class SIWESSessionViewSet(ModelViewSet):
    """CRUD for SIWES training sessions - administrators write, all read."""

    queryset = SIWESSession.objects.all()
    serializer_class = SIWESSessionSerializer
    permission_classes = [IsAdministratorOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = self.request.query_params.get("is_active")
        if is_active in ("true", "false"):
            queryset = queryset.filter(is_active=(is_active == "true"))
        return queryset

    def perform_create(self, serializer):
        session = serializer.save()
        audit(self.request.user, "SESSION CREATED", f"Created SIWES session '{session.name}'.")
        return session

    def perform_update(self, serializer):
        session = serializer.save()
        audit(self.request.user, "SESSION UPDATED", f"Updated SIWES session '{session.name}'.")
        return session

    def perform_destroy(self, instance):
        if instance.placements.exists():
            # Historical records must keep their link to the session.
            instance.is_active = False
            instance.save(update_fields=["is_active"])
            audit(
                self.request.user,
                "SESSION DEACTIVATED",
                f"Session '{instance.name}' was deactivated instead of deleted because it has placements.",
            )
            return None
        instance.delete()
        audit(self.request.user, "SESSION DELETED", f"Deleted SIWES session '{instance.name}'.")


class PlacementViewSet(ModelViewSet):
    """
    Placement management.

    One placement row per student (OneToOne). POST /api/core/placements/ with
    {"student": id, "organization": id, "supervisor": id, "siwes_session": id}
    assigns a new student. PATCH /api/core/placements/<id>/ re-assigns.
    """

    queryset = Placement.objects.select_related(
        "student__user", "organization", "supervisor__user", "siwes_session"
    )
    serializer_class = PlacementSerializer
    permission_classes = [IsAdministratorOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_supervisor_role:
            queryset = queryset.filter(supervisor=user.supervisor_profile)
        elif user.is_student_role:
            queryset = queryset.filter(student=user.student_profile)
        for param in ("is_active", "siwes_session", "supervisor", "organization"):
            value = self.request.query_params.get(param)
            if value not in (None, ""):
                queryset = queryset.filter(**{param: value})
        return queryset

    @staticmethod
    def _validate_ids(data, exempt_supervisor_id=None):
        """Make sure administrator-supplied ids actually exist (idempotent errors).

        Supervisors must be *approved* before they can be assigned to a
        student: pending or rejected registrations (and deactivated
        supervisors) are refused. `exempt_supervisor_id` keeps an existing
        placement working when its currently assigned supervisor is later
        deactivated - editing other fields must not force a re-assignment."""
        errors = {}
        if data.get("organization") and not Organization.objects.filter(pk=data["organization"]).exists():
            errors["organization"] = "Organization not found."
        if data.get("supervisor"):
            supervisor = SupervisorProfile.objects.filter(pk=data["supervisor"]).first()
            if supervisor is None:
                errors["supervisor"] = "Supervisor not found."
            elif (
                int(data["supervisor"]) != exempt_supervisor_id
                and (supervisor.is_pending or not supervisor.is_active or supervisor.rejected_at)
            ):
                errors["supervisor"] = "Only approved supervisors can be assigned to students."
        if data.get("siwes_session") and not SIWESSession.objects.filter(pk=data["siwes_session"]).exists():
            errors["siwes_session"] = "SIWES session not found."
        return errors

    def create(self, request, *args, **kwargs):
        errors = self._validate_ids(request.data)
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        student_id = request.data.get("student")
        if not student_id:
            return Response({"student": "Student id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            student = StudentProfile.objects.get(pk=student_id)
        except (StudentProfile.DoesNotExist, ValueError):
            return Response({"student": "Student not found."}, status=status.HTTP_400_BAD_REQUEST)
        if Placement.objects.filter(student=student).exists():
            return Response(
                {
                    "student": "This student already has a placement record. "
                    "Use PATCH /api/core/placements/<id>/ to re-assign."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        placement = serializer.save()
        audit(
            request.user,
            "PLACEMENT ASSIGNED",
            f"Assigned '{student}' to '{placement.organization.name if placement.organization else 'no organization'}'.",
        )
        # Tell the student and the supervisor about the new assignment using
        # the existing notification system.
        from notifications.utils import notify

        notify(
            student.user,
            "placement",
            "Placement assigned",
            "Your industrial training placement has been recorded. See your dashboard for details.",
            target_url="/pages/student-dashboard.html",
        )
        if placement.supervisor is not None:
            notify(
                placement.supervisor.user,
                "placement",
                "New student assigned",
                f"'{student}' was assigned to you for review.",
                target_url="/pages/supervisor-dashboard.html",
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        errors = self._validate_ids(
            request.data,
            exempt_supervisor_id=instance.supervisor_id
            if str(instance.supervisor_id or "") == str(request.data.get("supervisor") or "")
            else None,
        )
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        previous_supervisor_id = instance.supervisor_id
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        placement = serializer.save()
        audit(
            request.user,
            "PLACEMENT UPDATED",
            f"Updated placement #{placement.id} of student '{placement.student}'.",
        )
        # If the supervisor changed under an active placement, tell the new
        # supervisor (and the student) using the existing notification system.
        if placement.is_active and placement.supervisor_id != previous_supervisor_id:
            from notifications.utils import notify

            if placement.supervisor is not None:
                notify(
                    placement.supervisor.user,
                    "placement",
                    "New student assigned",
                    f"'{placement.student}' was assigned to you for review.",
                    target_url="/pages/supervisor-dashboard.html",
                )
            notify(
                placement.student.user,
                "placement",
                "Placement updated",
                f"Your supervisor is now '{placement.supervisor}'." if placement.supervisor
                else "Your placement was updated.",
                target_url="/pages/student-dashboard.html",
            )
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Deactivate instead of deleting; possible history preservation depends on
        the student's training records (logs/reports), so it is described in
        the audit entry.
        """
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        audit(
            request.user,
            "PLACEMENT DEACTIVATED",
            f"Deactivated placement #{instance.id} of student '{instance.student}'.",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="supervisor-options",
            permission_classes=[IsAuthenticated])
    def supervisor_options(self, request):
        """GET /api/core/placements/supervisor-options/ - students only.

        Slim directory of *approved* supervisors so a student who was assigned
        a supervisor outside SIWES Hub can identify them. Only names, job
        titles and departments are exposed (no contact or approval data)."""
        if not request.user.is_student_role:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        approved = (
            SupervisorProfile.objects
            .filter(is_active=True, is_pending=False, rejected_at__isnull=True)
            .select_related("user")
            .order_by("user__full_name")
        )
        options = [
            {
                "id": s.pk,
                "full_name": s.user.full_name or s.user.username,
                "title": s.title,
                "department": s.department,
            }
            for s in approved
        ]
        # If the student somehow already has a supervisor recorded, make sure
        # they can still see it labelled rather than silently re-picking.
        placement = getattr(getattr(request.user, "student_profile", None), "placement", None)
        if placement is not None and placement.supervisor_id:
            current = placement.supervisor
            current_id = current.pk
            options = [
                o for o in options if o["id"] != current_id
            ]
            options.insert(0, {
                "id": current_id,
                "full_name": current.user.full_name or current.user.username,
                "title": current.title,
                "department": current.department,
                "currently_assigned": True,
            })
        return Response(options)

    @action(detail=False, methods=["post"], url_path="select-supervisor",
            permission_classes=[IsAuthenticated])
    def select_supervisor(self, request):
        """POST /api/core/placements/select-supervisor/ - students only.

        For students whose supervisor was assigned *outside* SIWES Hub: they
        record that supervisor themselves. The pick takes effect immediately
        but is limited to approved supervisors, audited, and notified - the
        SIWES office can still edit the placement on the Students page."""
        if not request.user.is_student_role:
            return Response(
                {"detail": "Only students can select their own supervisor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        supervisor_id = request.data.get("supervisor")
        if not supervisor_id:
            return Response(
                {"supervisor": "Select the supervisor who was assigned to you."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        supervisor = SupervisorProfile.objects.select_related("user").filter(pk=supervisor_id).first()
        if supervisor is None:
            return Response({"supervisor": "Supervisor not found."}, status=status.HTTP_400_BAD_REQUEST)
        if supervisor.is_pending or not supervisor.is_active or supervisor.rejected_at:
            return Response(
                {"supervisor": "Only approved supervisors can be selected."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            student = request.user.student_profile
        except StudentProfile.DoesNotExist:
            return Response({"detail": "Student profile not found."}, status=status.HTTP_404_NOT_FOUND)
        placement = getattr(student, "placement", None)
        if placement is not None and not placement.is_active:
            return Response(
                {"detail": "Your previous placement is closed. Ask the SIWES office to reactivate it."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if placement is not None and placement.supervisor_id:
            if placement.supervisor_id == supervisor.pk:
                return Response(
                    {"detail": "You are already assigned to this supervisor."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"detail": "You are already assigned to a supervisor. "
                           "Contact the SIWES office if it needs to change."},
                status=status.HTTP_409_CONFLICT,
            )
        created = placement is None
        if created:
            placement = Placement(student=student, supervisor=supervisor, is_active=True)
            placement.save()
            audit(
                request.user,
                "PLACEMENT SELF-ASSIGNED",
                f"'{student}' recorded supervisor '{supervisor}' "
                f"(supervisor assigned outside SIWES Hub).",
            )
        else:
            placement.supervisor = supervisor
            placement.save(update_fields=["supervisor"])
            audit(
                request.user,
                "SUPERVISOR SELF-ASSIGNED",
                f"'{student}' selected supervisor '{supervisor}' for placement #{placement.id}.",
            )
        from notifications.utils import notify
        from django.contrib.auth import get_user_model

        notify(
            supervisor.user,
            "placement",
            "New student assigned",
            f"'{student}' selected you as their SIWES supervisor.",
            target_url="/pages/supervisor-dashboard.html",
        )
        notify(
            request.user,
            "placement",
            "Supervisor recorded",
            "'%s' is now recorded as your supervisor. The SIWES office can still "
            "update your placement if needed." % supervisor,
            target_url="/pages/student-dashboard.html",
        )
        for admin_user in get_user_model().objects.filter(role="admin", is_active=True):
            notify(
                admin_user,
                "placement",
                "Student picked a supervisor",
                f"'{student}' selected '{supervisor}' as their supervisor. Review it on the Students page.",
                target_url="/pages/students.html",
            )
        return Response(
            PlacementSerializer(placement).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AuditLogListView(APIView):
    """GET /api/core/audit/ - administrators only."""

    def get_permissions(self):
        # Imported lazily to avoid a circular import (accounts.views imports
        # from core at module level).
        from accounts.views import IsAdministrator

        return [IsAdministrator()]

    def get(self, request):
        from core.pagination import paginate_response

        return paginate_response(AuditLogSerializer, request, AuditLog.objects.all())
