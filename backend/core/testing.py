"""Shared test helpers for SIWES Hub application tests."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

PASSWORD = "Strong#Pass123"


class TestCaseBase(TestCase):
    """Common fixture: admin, two supervisors, one assigned student."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.admin = User.objects.create_user(
            username="admin", password=PASSWORD, role=User.ROLE_ADMIN,
            full_name="Test Admin", email="admin@test.edu",
        )
        cls.supervisor = User.objects.create_user(
            username="supervisor1", password=PASSWORD, role=User.ROLE_SUPERVISOR,
            full_name="Dr. Supervise One", email="sup1@test.edu",
        )
        cls.other_supervisor = User.objects.create_user(
            username="supervisor2", password=PASSWORD, role=User.ROLE_SUPERVISOR,
            full_name="Dr. Supervise Two", email="sup2@test.edu",
        )
        cls.student = User.objects.create_user(
            username="student1", password=PASSWORD, role=User.ROLE_STUDENT,
            full_name="Test Student", email="stu1@test.edu",
        )
        cls.student_other = User.objects.create_user(
            username="student2", password=PASSWORD, role=User.ROLE_STUDENT,
            full_name="Other Student", email="stu2@test.edu",
        )

        from supervisors.models import SupervisorProfile

        cls.supervisor_profile = SupervisorProfile.objects.create(user=cls.supervisor)
        cls.other_supervisor_profile = SupervisorProfile.objects.create(user=cls.other_supervisor)

        from students.models import StudentProfile

        cls.student_profile = StudentProfile.objects.create(
            user=cls.student, matric_number="2305999001"
        )
        cls.other_student_profile = StudentProfile.objects.create(
            user=cls.student_other, matric_number="2305999002"
        )

    @staticmethod
    def logged_client(user) -> Client:
        client = Client()
        client.force_login(user)
        return client
