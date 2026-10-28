"""
Student-facing and administrator-facing views.

Authorization summary:
* Students list/detail      -> admin sees all, supervisors only their assigned
* Own profile               -> student reads/patches permitted fields only
* Skills                    -> students manage their own, supervisors may read
* Student creation          -> administrators create user + profile in one call
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate_response
from core.utils import audit

from .models import Skill, StudentProfile
from .serializers import (
    SelfUpdateStudentProfileSerializer,
    SkillSerializer,
    StudentProfileSerializer,
)

User = get_user_model()


class StudentListCreateView(APIView):
    """GET /api/students/ (list, searchable) and POST (register a student)."""

    def _visible_queryset(self, request):
        queryset = StudentProfile.objects.select_related("user").all()
        if request.user.is_supervisor_role:
            queryset = queryset.filter(
                placement__is_active=True,
                placement__supervisor=request.user.supervisor_profile,
            )
        elif request.user.is_student_role:
            # Students may only see themselves in list contexts.
            queryset = queryset.filter(user=request.user)
        search = request.query_params.get("search")
        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(user__full_name__icontains=search)
                | Q(user__username__icontains=search)
                | Q(matric_number__icontains=search)
                | Q(department__icontains=search)
            )
        for param in ("department", "level"):
            value = request.query_params.get(param)
            if value:
                queryset = queryset.filter(**{f"{param}__iexact": value})
        is_active = request.query_params.get("is_active")
        if is_active in ("true", "false"):
            queryset = queryset.filter(is_active=(is_active == "true"))
        return queryset.order_by("user__full_name")

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Login required."}, status=status.HTTP_401_UNAUTHORIZED)
        if not (request.user.is_admin_role or request.user.is_supervisor_role or request.user.is_student_role):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        return paginate_response(StudentProfileSerializer, request, self._visible_queryset(request))

    def post(self, request):
        """Administrator creates user account + student profile together."""
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can register students."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        errors = {}
        username = (data.get("username") or "").strip()
        matric_number = (data.get("matric_number") or "").strip()
        password = data.get("password") or ""
        full_name = (data.get("full_name") or "").strip()

        if not username:
            errors["username"] = "Username is required."
        elif User.objects.filter(username__iexact=username).exists():
            errors["username"] = "That username is already taken."
        if not matric_number:
            errors["matric_number"] = "Matriculation number is required."
        elif "\n" in matric_number or StudentProfile.objects.filter(matric_number__iexact=matric_number).exists():
            errors["matric_number"] = "Matriculation number must be unique."
        if not full_name:
            errors["full_name"] = "Full name is required."
        if len(password) < 6:
            errors["password"] = "Password must be at least 6 characters."
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = User(
                username=username,
                role=User.ROLE_STUDENT,
                full_name=full_name,
                email=(data.get("email") or "").strip(),
                phone=(data.get("phone") or "").strip(),
            )
            user.set_password(password)
            user.save()

            profile = StudentProfile(
                user=user,
                matric_number=matric_number,
                department=(data.get("department") or "").strip(),
                faculty=(data.get("faculty") or "").strip(),
                level=(data.get("level") or "").strip(),
            )
            for field in ("training_start_date", "training_end_date"):
                if data.get(field):
                    profile.__setattr__(field, data[field])
            profile.save()

        audit(request.user, "STUDENT CREATED", f"Registered student '{full_name}' ({matric_number}).")
        return Response(StudentProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class StudentDetailView(APIView):
    """GET/PATCH/DELETE one student (admin full, supervisor read assigned)."""

    def _get_visible_student(self, request, pk):
        try:
            profile = StudentProfile.objects.select_related("user").get(pk=pk)
        except (StudentProfile.DoesNotExist, ValueError):
            return None
        if request.user.is_admin_role:
            return profile
        if request.user.is_supervisor_role:
            placement = getattr(profile, "placement", None)
            if (
                placement
                and placement.is_active
                and placement.supervisor == request.user.supervisor_profile
            ):
                return profile
        return None

    def get(self, request, pk):
        profile = self._get_visible_student(request, pk)
        if profile is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(StudentProfileSerializer(profile).data)

    def patch(self, request, pk):
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can edit students."}, status=status.HTTP_403_FORBIDDEN)
        profile = self._get_visible_student(request, pk)
        if profile is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = StudentProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # Split nested user fields (full_name/email/phone) for writing.
        user_data = serializer.validated_data.pop("user", {}) if "user" in serializer.validated_data else {}
        with transaction.atomic():
            instance = serializer.save()
            user = instance.user
            for field in ("full_name", "email", "phone"):
                if field in user_data:
                    setattr(user, field, user_data[field])
            user.save()
        audit(request.user, "STUDENT UPDATED", f"Updated student '{instance.matric_number}'.")
        return Response(StudentProfileSerializer(instance).data)

    def delete(self, request, pk):
        """Deactivate instead of deleting to keep history intact (logs etc.)."""
        if not request.user.is_admin_role:
            return Response({"detail": "Only administrators can do this."}, status=status.HTTP_403_FORBIDDEN)
        profile = self._get_visible_student(request, pk)
        if profile is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        profile.is_active = False
        profile.save(update_fields=["is_active"])
        audit(request.user, "STUDENT DEACTIVATED", f"Deactivated student '{profile.matric_number}'.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyStudentProfileView(APIView):
    """GET/PATCH /api/students/me/ - student's own permitted profile fields."""

    def get(self, request):
        if not request.user.is_student_role:
            return Response({"detail": "Student account required."}, status=status.HTTP_403_FORBIDDEN)
        profile = request.user.student_profile
        return Response(SelfUpdateStudentProfileSerializer(profile).data)

    def patch(self, request):
        if not request.user.is_student_role:
            return Response({"detail": "Student account required."}, status=status.HTTP_403_FORBIDDEN)
        profile = request.user.student_profile
        serializer = SelfUpdateStudentProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        audit(request.user, "PROFILE UPDATED", f"Student '{request.user.username}' updated their profile.")
        return Response(SelfUpdateStudentProfileSerializer(instance).data)


# --------------------------------------------------------------------------- #
# Skills
# --------------------------------------------------------------------------- #
class IsOwnStudent(permissions.BasePermission):
    """Object-level: a student may only touch their own records."""

    def has_object_permission(self, request, view, obj):
        student = getattr(obj, "student", None)
        return (
            request.user.is_authenticated
            and request.user.is_student_role
            and student == request.user.student_profile
        )


class SkillListCreateView(APIView):
    """GET (own skills; supervisor may read assigned students') and POST."""

    def get(self, request):
        if request.user.is_student_role:
            queryset = Skill.objects.filter(student=request.user.student_profile)
        elif request.user.is_supervisor_role:
            from core.utils import get_supervisor_students

            queryset = Skill.objects.filter(
                student__in=get_supervisor_students(request.user.supervisor_profile)
            )
        elif request.user.is_admin_role:
            queryset = Skill.objects.all()
        else:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        return Response(SkillSerializer(queryset.order_by("-date_learned"), many=True).data)

    def post(self, request):
        if not request.user.is_student_role:
            return Response({"detail": "Only students can add skills."}, status=status.HTTP_403_FORBIDDEN)
        data = dict(request.data)
        data["student"] = request.user.student_profile.pk  # server-side owner
        serializer = SkillSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        # Duplicate check (unique constraint message is friendlier here).
        name = serializer.validated_data.get("name")
        if Skill.objects.filter(student=request.user.student_profile, name__iexact=name).exists():
            return Response({"name": "You already recorded this skill."}, status=status.HTTP_400_BAD_REQUEST)

        skill = serializer.save(student=request.user.student_profile)
        return Response(SkillSerializer(skill).data, status=status.HTTP_201_CREATED)


class SkillDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated, IsOwnStudent]

    def get_queryset(self):
        # Students only ever reach their own skill rows through this view.
        return Skill.objects.filter(student=self.request.user.student_profile)
