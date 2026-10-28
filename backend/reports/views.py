"""
Weekly report API views - mirrors the daily log workflow.

Endpoints (mounted under /api/reports/):
  GET/POST /, GET/PATCH/DELETE /<id>/, POST /<id>/submit/, POST /<id>/review/
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate_response
from core.utils import audit, get_supervisor_students
from notifications.utils import notify

from .models import WeeklyReport
from .serializers import ReportReviewSerializer, WeeklyReportSerializer


class WeeklyReportListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _visible_reports(self, request):
        user = request.user
        if user.is_student_role:
            queryset = WeeklyReport.objects.filter(student=user.student_profile)
        elif user.is_supervisor_role:
            supervisor_students = get_supervisor_students(user.supervisor_profile)
            queryset = WeeklyReport.objects.filter(student__in=supervisor_students)
        elif user.is_admin_role:
            queryset = WeeklyReport.objects.all()
        else:
            queryset = WeeklyReport.objects.none()

        if request.query_params.get("status"):
            queryset = queryset.filter(status=request.query_params["status"])
        if request.query_params.get("student"):
            queryset = queryset.filter(student_id=request.query_params["student"])
        if request.query_params.get("date_from"):
            queryset = queryset.filter(week_start__gte=request.query_params["date_from"])
        if request.query_params.get("date_to"):
            queryset = queryset.filter(week_start__lte=request.query_params["date_to"])
        return queryset.select_related("student__user").order_by("-week_start")

    def get(self, request):
        return paginate_response(WeeklyReportSerializer, request, self._visible_reports(request))

    def post(self, request):
        if not request.user.is_student_role:
            return Response(
                {"detail": "Only students can create weekly reports."},
                status=status.HTTP_403_FORBIDDEN,
            )
        payload = dict(request.data)
        payload["student"] = request.user.student_profile.pk
        if payload.get("week_start"):
            existing = WeeklyReport.objects.filter(
                student=request.user.student_profile, week_start=payload["week_start"]
            )
            if existing.exists():
                return Response(
                    {"week_start": "You already have a report for that week."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        serializer = WeeklyReportSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        report = serializer.save(student=request.user.student_profile, status=WeeklyReport.STATUS_DRAFT)
        # Default the week end automatically when not supplied.
        if not report.week_end:
            report.week_end = report.week_start + timezone.timedelta(days=6)
            report.save(update_fields=["week_end", "updated_at"])
        return Response(WeeklyReportSerializer(report).data, status=status.HTTP_201_CREATED)


class WeeklyReportDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_visible(self, request, pk):
        try:
            report = WeeklyReport.objects.select_related("student__user").get(pk=pk)
        except (WeeklyReport.DoesNotExist, ValueError):
            return None
        user = request.user
        if user.is_admin_role:
            return report
        if user.is_student_role and report.student_id == user.student_profile.id:
            return report
        if user.is_supervisor_role and report.student in get_supervisor_students(user.supervisor_profile):
            return report
        return None

    def get(self, request, pk):
        report = self._get_visible(request, pk)
        if report is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(WeeklyReportSerializer(report).data)

    def patch(self, request, pk):
        report = self._get_visible(request, pk)
        if report is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not (request.user.is_student_role and report.student_id == request.user.student_profile.id):
            return Response(
                {"detail": "Only the student who owns this report can edit it."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not report.is_editable:
            return Response(
                {"detail": "This report has already been reviewed and can no longer be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload = dict(request.data)
        payload["student"] = report.student_id
        serializer = WeeklyReportSerializer(report, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(WeeklyReportSerializer(instance).data)

    def delete(self, request, pk):
        report = self._get_visible(request, pk)
        if report is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not (request.user.is_student_role and report.student_id == request.user.student_profile.id):
            return Response({"detail": "Only the owner can delete this report."}, status=status.HTTP_403_FORBIDDEN)
        if not report.is_editable:
            return Response({"detail": "Only drafts can be deleted."}, status=status.HTTP_400_BAD_REQUEST)
        report.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WeeklyReportSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_student_role:
            return Response({"detail": "Only students can submit reports."}, status=status.HTTP_403_FORBIDDEN)
        try:
            report = WeeklyReport.objects.get(pk=pk, student=request.user.student_profile)
        except (WeeklyReport.DoesNotExist, ValueError):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if report.status not in (WeeklyReport.STATUS_DRAFT, WeeklyReport.STATUS_REJECTED):
            return Response({"detail": "This report has already been submitted."}, status=status.HTTP_400_BAD_REQUEST)
        report.status = WeeklyReport.STATUS_SUBMITTED
        report.submitted_at = timezone.now()
        report.save(update_fields=["status", "submitted_at", "updated_at"])
        audit(request.user, "REPORT SUBMITTED", f"Weekly report #{report.id} (week of {report.week_start}) submitted.")

        placement = getattr(report.student, "placement", None)
        if placement and placement.supervisor:
            notify(
                recipient=placement.supervisor.user,
                kind="report_submitted",
                title="New weekly report submitted",
                body=f"{report.student} submitted a weekly report for week {report.week_start} to {report.week_end}.",
                target_url=f"pages/weekly-reports.html?mode=review&id={report.id}",
            )
        return Response(WeeklyReportSerializer(report).data)


class WeeklyReportReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_supervisor_role:
            return Response({"detail": "Only supervisors can review weekly reports."}, status=status.HTTP_403_FORBIDDEN)
        try:
            report = WeeklyReport.objects.select_related("student__user").get(pk=pk)
        except (WeeklyReport.DoesNotExist, ValueError):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        supervisor_students = get_supervisor_students(request.user.supervisor_profile)
        if report.student not in supervisor_students or report.status != WeeklyReport.STATUS_SUBMITTED:
            return Response(
                {"detail": "This report is not assigned to you, or it is not awaiting review."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ReportReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        comment = serializer.validated_data.get("comment", "")
        if decision == "reject" and not comment.strip():
            return Response(
                {"comment": "A reason is required when rejecting a report."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        report.status = (
            WeeklyReport.STATUS_APPROVED if decision == "approve" else WeeklyReport.STATUS_REJECTED
        )
        report.supervisor = request.user.supervisor_profile
        report.supervisor_comment = comment
        report.reviewed_at = timezone.now()
        report.save(update_fields=["status", "supervisor", "supervisor_comment", "reviewed_at", "updated_at"])
        audit(
            request.user,
            "REPORT REVIEWED",
            f"Weekly report #{report.id} (week of {report.week_start}) of '{report.student}' -> {report.status}.",
        )
        body = f"Your weekly report for {report.week_start} was {report.status}."
        if report.supervisor_comment:
            body += f' Supervisor comment: "{report.supervisor_comment}"'
        notify(
            recipient=report.student.user,
            kind="report_reviewed",
            title="Weekly report approved" if decision == "approve" else "Weekly report rejected",
            body=body,
            target_url=f"pages/weekly-reports.html?id={report.id}",
        )
        return Response(WeeklyReportSerializer(report).data)
