"""Utility helpers shared by every SIWES Hub application."""
from .audit import audit, record_audit_log  # noqa: F401


def get_active_placement(student_profile):
    """Return the active Placement of a student profile, or None."""
    if hasattr(student_profile, "placement") and student_profile.placement.is_active:
        return student_profile.placement
    return None


def get_supervisor_students(supervisor_profile):
    """Return the student profiles currently assigned to a supervisor."""
    from students.models import StudentProfile

    return list(
        StudentProfile.objects.exclude(is_active=False).filter(
            placement__is_active=True,
            placement__supervisor=supervisor_profile,
        )
    )
