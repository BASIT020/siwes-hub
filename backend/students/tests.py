"""Student management (administrator) tests."""
from rest_framework.test import APIClient

from accounts.models import User
from core.testing import TestCaseBase
from students.models import StudentProfile


class StudentManagementTests(TestCaseBase):
    def test_admin_registers_student_with_profile(self):
        client = APIClient()
        client.force_login(self.admin)
        response = client.post(
            "/api/students/",
            {
                "username": "newstudent",
                "full_name": "New Student",
                "matric_number": "2305999003",
                "password": "StrongPass#9",
                "department": "Computer Science",
                "level": "ND1",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        profile = StudentProfile.objects.get(matric_number="2305999003")
        self.assertEqual(profile.user.role, User.ROLE_STUDENT)
        self.assertTrue(profile.user.check_password("StrongPass#9"))

    def test_student_cannot_register_students(self):
        client = APIClient()
        client.force_login(self.student)
        response = client.post(
            "/api/students/",
            {
                "username": "evil",
                "full_name": "Evil Student",
                "matric_number": "2305999004",
                "password": "whatever1",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="evil").exists())

    def test_duplicate_matric_rejected(self):
        client = APIClient()
        client.force_login(self.admin)
        response = client.post(
            "/api/students/",
            {
                "username": "another",
                "full_name": "Another Student",
                "matric_number": "2305999001",  # already used
                "password": "StrongPass#9",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("matric_number", response.json())

    def test_admin_updates_student(self):
        client = APIClient()
        client.force_login(self.admin)
        response = client.patch(
            f"/api/students/{self.student_profile.id}/",
            {"department": "Software Engineering"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.student_profile.refresh_from_db()
        self.assertEqual(self.student_profile.department, "Software Engineering")

    def test_search_filters_students(self):
        client = APIClient()
        client.force_login(self.admin)
        response = client.get("/api/students/?search=2305999001")
        data = response.json()
        results = data if isinstance(data, list) else data.get("results", [])
        self.assertEqual(len(results), 1)
