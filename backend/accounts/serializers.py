"""Serializers for authentication and user management."""
from django.db import transaction
from rest_framework import serializers

from .models import User


class UserSummarySerializer(serializers.ModelSerializer):
    """Compact representation of a user (used in lists and nested fields)."""

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email", "role", "phone", "is_active"]


class AuthUserSerializer(serializers.ModelSerializer):
    """Returned to the frontend after login / on /me so the UI knows the role."""

    student_id = serializers.SerializerMethodField()
    supervisor_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "email",
            "phone",
            "role",
            "is_active",
            "student_id",
            "supervisor_id",
        ]

    def get_student_id(self, obj):
        if obj.is_student_role and hasattr(obj, "student_profile"):
            return obj.student_profile.pk
        return None

    def get_supervisor_id(self, obj):
        if obj.is_supervisor_role and hasattr(obj, "supervisor_profile"):
            return obj.supervisor_profile.pk
        return None


class PasswordResetSerializer(serializers.Serializer):
    """Input for the administrator 'reset user password' endpoint."""

    new_password = serializers.CharField(min_length=6, write_only=True)

    def validate_new_password(self, value):
        from django.contrib.auth.password_validation import validate_password

        # The target user is attached by the view.
        user = self.context.get("target_user")
        validate_password(value, user=user)
        return value


# --------------------------------------------------------------------------- #
# Public self-registration (students and supervisors only; the role is fixed
# server-side in each serializer, never taken from the payload).
# --------------------------------------------------------------------------- #
class ProfileUpdateSerializer(serializers.Serializer):
    """Self-service edit of the signed-in account's identity details
    (username, full name, email). Uniqueness is enforced case-insensitively,
    excluding the user's own current values. The password is NOT editable
    here - it has its own endpoint (/api/auth/change-password/) so a stolen
    session cannot take over the account silently."""

    username = serializers.CharField(max_length=150, trim_whitespace=True)
    full_name = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField(trim_whitespace=True, required=False, allow_blank=True)

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError("Username is required.")
        if len(username) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters.")
        taken = User.objects.filter(username__iexact=username)
        if self.instance is not None:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("That username is already taken. Choose another.")
        return username

    def validate_full_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Full name is required.")
        return value.strip()

    def validate_email(self, value):
        email = value.strip().lower()
        taken = User.objects.filter(email__iexact=email)
        if self.instance is not None:
            taken = taken.exclude(pk=self.instance.pk)
        if email and taken.exists():
            raise serializers.ValidationError(
                "That email address is already registered on another account."
            )
        return email

    def update(self, instance, validated_data):
        for field in ("username", "full_name", "email"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save(update_fields=["username", "full_name", "email"])
        return instance


class RegistrationSerializer(serializers.Serializer):
    """Shared behaviour for both registration forms."""

    full_name = serializers.CharField(max_length=150, trim_whitespace=True)
    email = serializers.EmailField(trim_whitespace=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False, label="Confirm password")

    # Roles a visitor may self-register as. Administrators are created by the
    # bootstrap command only - there is no public path to the admin role.
    allowed_role = None

    def validate_full_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Full name is required.")
        if not all(ch.isalpha() or ch in " '-" for ch in value.strip().replace(" ", "")):
            raise serializers.ValidationError(
                "Full name may contain letters, spaces, hyphens and apostrophes only."
            )
        return value.strip()

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "That email address is already registered. Sign in instead or use another email."
            )
        return email

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password

        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError({"password2": "The two passwords do not match."})
        return attrs

    def _build_user(self, username, validated_data, is_active=True):
        return User(
            username=username,
            role=self.allowed_role,  # fixed server-side: never from the payload
            full_name=validated_data["full_name"],
            email=validated_data["email"],
            is_active=is_active,
        )


class StudentRegistrationSerializer(RegistrationSerializer):
    """Public registration form for students."""

    allowed_role = User.ROLE_STUDENT

    matric_number = serializers.CharField(max_length=30, trim_whitespace=True)
    department = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    faculty = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    level = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")

    def validate_matric_number(self, value):
        matric = value.strip()
        if not matric:
            raise serializers.ValidationError("Matriculation number is required.")
        from django.core.validators import RegexValidator

        RegexValidator(
            r"^[A-Za-z0-9/\-.]+$",
            "Matriculation number may contain letters, digits, slashes, dots and hyphens.",
        )(matric)
        from students.models import StudentProfile

        if StudentProfile.objects.filter(matric_number__iexact=matric).exists():
            raise serializers.ValidationError("That matriculation number is already registered.")
        # The matric number doubles as the sign-in username.
        if User.objects.filter(username__iexact=matric).exists():
            raise serializers.ValidationError(
                "That matriculation number is already registered. Sign in instead or use another number."
            )
        return matric

    def create(self, validated_data):
        from students.models import StudentProfile

        user = self._build_user(validated_data["matric_number"], validated_data, is_active=True)
        user.set_password(validated_data["password"])
        with transaction.atomic():
            user.save()
            StudentProfile.objects.create(
                user=user,
                matric_number=validated_data["matric_number"],
                department=validated_data.get("department", ""),
                faculty=validated_data.get("faculty", ""),
                level=validated_data.get("level", ""),
            )
        return user


class SupervisorRegistrationSerializer(RegistrationSerializer):
    """Public registration form for supervisors (needs administrator approval)."""

    allowed_role = User.ROLE_SUPERVISOR

    username = serializers.CharField(max_length=150, trim_whitespace=True)
    title = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    staff_id = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    department = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError("Username is required.")
        if len(username) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters.")
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError("That username is already taken. Choose another.")
        return username

    def validate_title(self, value):
        if value.strip() and not value.strip().rstrip(".").isalpha():
            raise serializers.ValidationError("Title may contain letters only (e.g. Dr., Mr.).")
        return value.strip()

    def create(self, validated_data):
        from supervisors.models import SupervisorProfile

        user = self._build_user(validated_data["username"], validated_data, is_active=False)
        user.set_password(validated_data["password"])
        with transaction.atomic():
            user.save()
            SupervisorProfile.objects.create(
                user=user,
                staff_id=validated_data.get("staff_id", ""),
                title=validated_data.get("title", ""),
                department=validated_data.get("department", ""),
                is_active=False,  # mirrors the pending user account
                is_pending=True,
            )
        return user
