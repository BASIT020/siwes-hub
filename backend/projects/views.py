"""
Project API views.

* GET  /me/         - the caller's own project (students)
* PUT/PATCH /me/    - edit while not submitted
* POST /me/submit/  - send for supervisor review
* GET  /            - supervisors: projects of assigned students; admins: all
* POST /<id>/review/ - assigned supervisor approves or rejects
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate_response
from core.utils import audit, get_supervisor_students
from notifications.utils import notify

from .models import StudentProject
from .serializers import ProjectReviewSerializer, StudentProjectSerializer


def _supervisor_students(user):
    return get_supervisor_students(user.supervisor_profile)


class MyProjectView(APIView):
    """GET/PATCH /api/projects/me/ - student maintains their own project."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_student_role:
            return Response({"detail": "Student account required."}, status=status.HTTP_403_FORBIDDEN)
        project = StudentProject.objects.filter(student=request.user.student_profile).first()
        if project is None:
            # 200 with null so the frontend can show "create project" UI.
            return Response({"detail": None, "project": None}, status=status.HTTP_200_OK)
        return Response(StudentProjectSerializer(project).data)

    def post(self, request):
        """POST creates the project (Retrieval returns 404-style empty)."""
        if not request.user.is_student_role:
            return Response({"detail": "Student account required."}, status=status.HTTP_403_FORBIDDEN)
        if StudentProject.objects.filter(student=request.user.student_profile).exists():
            return Response(
                {"detail": "You already have a project. Use PATCH to edit it."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (request.data.get("title") or "").strip():
            return Response({"title": "A project title is required."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = StudentProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.save(
            student=request.user.student_profile,
            review_status=StudentProject.REVIEW_NOT_SUBMITTED,
        )
        audit(request.user, "PROJECT CREATED", f"Student '{request.user.username}' created project '{project.title}'.")
        return Response(StudentProjectSerializer(project).data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        if not request.user.is_student_role:
            return Response({"detail": "Student account required."}, status=status.HTTP_403_FORBIDDEN)
        project = StudentProject.objects.filter(student=request.user.student_profile).first()
        if project is None:
            return self.post(request)  # first save through POST-equivalent logic
        if not project.is_editable:
            return Response(
                {"detail": "This project is awaiting review or already approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = StudentProjectSerializer(project, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(StudentProjectSerializer(instance).data)


class MyProjectSubmitView(APIView):
    """POST /api/projects/me/submit/ - send the project for review."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_student_role:
            return Response({"detail": "Student account required."}, status=status.HTTP_403_FORBIDDEN)
        project = StudentProject.objects.filter(student=request.user.student_profile).first()
        if project is None:
            return Response({"detail": "Create your project first."}, status=status.HTTP_400_BAD_REQUEST)
        if project.review_status not in (
            StudentProject.REVIEW_NOT_SUBMITTED,
            StudentProject.REVIEW_REJECTED,
        ):
            return Response({"detail": "This project has already been submitted."}, status=status.HTTP_400_BAD_REQUEST)
        project.review_status = StudentProject.REVIEW_SUBMITTED
        project.submitted_at = timezone.now()
        project.save(update_fields=["review_status", "submitted_at", "updated_at"])
        audit(request.user, "PROJECT SUBMITTED", f"Project '{project.title}' submitted for review.")

        placement = getattr(project.student, "placement", None)
        if placement and placement.supervisor:
            notify(
                recipient=placement.supervisor.user,
                kind="project_submitted",
                title="New project submitted for review",
                body=f"{project.student} submitted the project '{project.title}' for review.",
                target_url=f"pages/projects.html?mode=review&id={project.id}",
            )
        return Response(StudentProjectSerializer(project).data)


class ProjectListView(APIView):
    """GET /api/projects/ - supervisor sees assigned students' projects, admin all."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_supervisor_role:
            queryset = StudentProject.objects.filter(student__in=_supervisor_students(user))
        elif user.is_admin_role:
            queryset = StudentProject.objects.all()
        else:
            return Response({"detail": "Use /api/projects/me/ for your own project."}, status=status.HTTP_403_FORBIDDEN)
        if request.query_params.get("review_status"):
            queryset = queryset.filter(review_status=request.query_params["review_status"])
        students_param = request.query_params.get("student")
        if students_param:
            queryset = queryset.filter(student_id=students_param)
        return paginate_response(
            StudentProjectSerializer, request, queryset.select_related("student__user")
        )


class ProjectReviewView(APIView):
    """POST /api/projects/<id>/review/ - assigned supervisor reviews the project."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_supervisor_role:
            return Response({"detail": "Only supervisors can review projects."}, status=status.HTTP_403_FORBIDDEN)
        try:
            project = StudentProject.objects.select_related("student__user").get(pk=pk)
        except (StudentProject.DoesNotExist, ValueError):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if project.student not in _supervisor_students(request.user) or project.review_status != StudentProject.REVIEW_SUBMITTED:
            return Response(
                {"detail": "This project is not assigned to you, or it is not awaiting review."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ProjectReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        comment = serializer.validated_data.get("comment", "")
        if decision == "reject" and not comment.strip():
            return Response(
                {"comment": "A reason is required when rejecting a project."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project.review_status = (
            StudentProject.REVIEW_APPROVED if decision == "approve" else StudentProject.REVIEW_REJECTED
        )
        if decision == "approve":
            project.status = "completed"
        project.supervisor = request.user.supervisor_profile
        project.supervisor_comment = comment
        project.reviewed_at = timezone.now()
        project.save(
            update_fields=[
                "review_status", "status", "supervisor", "supervisor_comment", "reviewed_at", "updated_at"
            ]
        )
        audit(
            request.user,
            "PROJECT REVIEWED",
            f"Project '{project.title}' of '{project.student}' -> {project.review_status}.",
        )
        body = f"Your project '{project.title}' was {project.review_status.replace('_', ' ')}."
        if project.supervisor_comment:
            body += f' Supervisor comment: "{project.supervisor_comment}"'
        notify(
            recipient=project.student.user,
            kind="project_reviewed",
            title="Project approved" if decision == "approve" else "Project rejected",
            body=body,
            target_url="pages/projects.html",
        )
        return Response(StudentProjectSerializer(project).data)
