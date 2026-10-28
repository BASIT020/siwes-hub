"""
Attendance API views.

* GET  /            - students see their own records (+summary), supervisors see
                      their assigned students, admins see everything.
* POST /            - supervisors (assigned students only) and admins record.
* PATCH /<id>/      - correct status/note within the same day policy; the
                      supervisor doing it is audited.
Summaries are computed live from the same records - never hard-coded.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate_response
from core.utils import audit, get_supervisor_students
from notifications.utils import notify

from .models import Attendance
from .serializers import AttendanceSerializer
from students.models import StudentProfile


def attendance_summary(student_profile):
    qs = Attendance.objects.filter(student=student_profile)
    total = qs.count()
    present = qs.filter(status=Attendance.STATUS_PRESENT).count()
    late = qs.filter(status=Attendance.STATUS_LATE).count()
    absent = qs.filter(status=Attendance.STATUS_ABSENT).count()
    excused = qs.filter(status=Attendance.STATUS_EXCUSED).count()
    rate = round((present / total) * 100) if total else 0
    return {
        "total_days": total,
        "present": present,
        "late": late,
        "absent": absent,
        "excused": excused,
        "attendance_rate": rate,
    }


class AttendanceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_student_role:
            queryset = Attendance.objects.filter(student=user.student_profile)
        elif user.is_supervisor_role:
            queryset = Attendance.objects.filter(
                student__in=get_supervisor_students(user.supervisor_profile)
            )
        elif user.is_admin_role:
            queryset = Attendance.objects.all()
        else:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        if request.query_params.get("date"):
            queryset = queryset.filter(date=request.query_params["date"])
        if request.query_params.get("status"):
            queryset = queryset.filter(status=request.query_params["status"])
        if request.query_params.get("student"):
            queryset = queryset.filter(student_id=request.query_params["student"])
        if request.query_params.get("date_from"):
            queryset = queryset.filter(date__gte=request.query_params["date_from"])
        if request.query_params.get("date_to"):
            queryset = queryset.filter(date__lte=request.query_params["date_to"])

        payload = paginate_response(AttendanceSerializer, request, queryset)
        return payload

    def post(self, request):
        user = request.user
        if not (user.is_supervisor_role or user.is_admin_role):
            return Response(
                {"detail": "Only supervisors (or administrators) can record attendance."},
                status=status.HTTP_403_FORBIDDEN,
            )
        payload = dict(request.data)
        student_id = payload.get("student")
        if not student_id:
            return Response({"student": "Student is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = StudentProfile.objects.get(pk=student_id)
        except (StudentProfile.DoesNotExist, ValueError):
            return Response({"student": "Student not found."}, status=status.HTTP_400_BAD_REQUEST)

        # A supervisor may only record attendance for their own assigned students.
        if user.is_supervisor_role and student not in get_supervisor_students(user.supervisor_profile):
            return Response(
                {"detail": "That student is not assigned to you."}, status=status.HTTP_403_FORBIDDEN
            )
        if Attendance.objects.filter(student=student, date=payload.get("date") or timezone.localdate()).exists():
            return Response(
                {"date": "Attendance for that student/date already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AttendanceSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(
            recorded_by=user,
            student=student,
            verified_by=user.supervisor_profile if user.is_supervisor_role else None,
            verified_at=timezone.now() if user.is_supervisor_role else None,
        )
        audit(
            user,
            "ATTENDANCE RECORDED",
            f"Attendance for '{student}' on {record.date} recorded as {record.status}.",
        )
        notify(
            recipient=student.user,
            kind="attendance",
            title="Attendance recorded",
            body=f"Your attendance for {record.date} was recorded as '{record.get_status_display()}'.",
            target_url="pages/attendance.html",
        )
        return Response(AttendanceSerializer(record).data, status=status.HTTP_201_CREATED)


class AttendanceSummaryView(APIView):
    """GET /api/attendance/summary/?student=<id> - live computed attendance stats.

    Students receive their own summary; supervisors/admins may request one for
    a student they are allowed to see.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_student_role:
            return Response(attendance_summary(user.student_profile))
        if user.is_supervisor_role:
            student_id = request.query_params.get("student")
            if not student_id:
                return Response(
                    {"detail": "student query parameter is required for supervisors."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                student = StudentProfile.objects.get(pk=student_id)
            except (StudentProfile.DoesNotExist, ValueError):
                return Response({"detail": "Student not found."}, status=status.HTTP_404_NOT_FOUND)
            if student not in get_supervisor_students(user.supervisor_profile):
                return Response({"detail": "That student is not assigned to you."}, status=status.HTTP_403_FORBIDDEN)
            return Response(attendance_summary(student))
        if user.is_admin_role:
            # Whole-programme summary
            qs = Attendance.objects.all()
            total = qs.count()
            present = qs.filter(status=Attendance.STATUS_PRESENT).count()
            return Response(
                {
                    "total_days": total,
                    "present": present,
                    "late": qs.filter(status=Attendance.STATUS_LATE).count(),
                    "absent": qs.filter(status=Attendance.STATUS_ABSENT).count(),
                    "excused": qs.filter(status=Attendance.STATUS_EXCUSED).count(),
                    "attendance_rate": round((present / total) * 100) if total else 0,
                }
            )
        return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)


class AttendanceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_visible(self, request, pk):
        try:
            record = Attendance.objects.get(pk=pk)
        except (Attendance.DoesNotExist, ValueError):
            return None
        user = request.user
        if user.is_admin_role:
            return record
        if user.is_student_role and record.student_id == user.student_profile.id:
            return record
        if user.is_supervisor_role and record.student in get_supervisor_students(user.supervisor_profile):
            return record
        return None

    def get(self, request, pk):
        record = self._get_visible(request, pk)
        if record is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AttendanceSerializer(record).data)

    def patch(self, request, pk):
        """Allow limited correction of status/note; audited and re-verified."""
        record = self._get_visible(request, pk)
        if record is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        user = request.user
        if not (user.is_admin_role or (user.is_supervisor_role and record.student in get_supervisor_students(user.supervisor_profile))):
            return Response(
                {"detail": "Attendance can only be corrected by a supervisor (or administrator)."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AttendanceSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        if user.is_supervisor_role:
            updated.verified_by = user.supervisor_profile
            updated.verified_at = timezone.now()
            updated.save(update_fields=["verified_by", "verified_at"])
        audit(
            user,
            "ATTENDANCE UPDATED",
            f"Attendance of '{updated.student}' on {updated.date} corrected to {updated.status}.",
        )
        return Response(AttendanceSerializer(updated).data)
