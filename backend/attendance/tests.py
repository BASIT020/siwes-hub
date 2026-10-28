"""Attendance permission and integrity tests."""
from datetime import date

from rest_framework.test import APIClient

from attendance.models import Attendance
from core.testing import TestCaseBase
from students.models import StudentProfile


class AttendanceTests(TestCaseBase):
    def setUp(self):
        self.today = date.today()

    def _place_student(self):
        from organizations.models import Organization
        from core.models import Placement, SIWESSession

        organization, _ = Organization.objects.get_or_create(name="Attendance Org")
        session = SIWESSession.objects.create(
            name="Att. Session", start_date=self.today, end_date=self.today
        )
        Placement.objects.create(
            student=self.student_profile,
            organization=organization,
            supervisor=self.supervisor_profile,
            siwes_session=session,
            is_active=True,
        )

    def test_student_cannot_record_own_attendance(self):
        client = APIClient()
        client.force_login(self.student)
        response = client.post(
            "/api/attendance/",
            {"student": self.student_profile.id, "date": self.today.isoformat(), "status": "present"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_assigned_supervisor_records_and_verifies(self):
        self._place_student()
        client = APIClient()
        client.force_login(self.supervisor)
        response = client.post(
            "/api/attendance/",
            {
                "student": self.student_profile.id,
                "date": self.today.isoformat(),
                "status": "late",
                "note": "Came by 9am",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        record = Attendance.objects.get(pk=response.json()["id"])
        self.assertEqual(record.status, Attendance.STATUS_LATE)
        self.assertEqual(record.verified_by, self.supervisor_profile)
        self.assertEqual(record.recorded_by, self.supervisor)
        self.assertIsNotNone(record.verified_at)

    def test_unassigned_supervisor_cannot_record(self):
        client = APIClient()
        client.force_login(self.other_supervisor)
        response = client.post(
            "/api/attendance/",
            {"student": self.student_profile.id, "date": self.today.isoformat(), "status": "present"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_duplicate_student_date_rejected(self):
        self._place_student()
        client = APIClient()
        client.force_login(self.supervisor)
        first = client.post(
            "/api/attendance/",
            {"student": self.student_profile.id, "date": self.today.isoformat(), "status": "present"},
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 201)
        second = client.post(
            "/api/attendance/",
            {"student": self.student_profile.id, "date": self.today.isoformat(), "status": "present"},
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 400)

    def test_student_sees_only_own_records(self):
        client = APIClient()
        client.force_login(self.student_other)
        response = client.get(
            f"/api/attendance/?student={self.student_profile.id}"
        )
        data = response.json()
        results = data if isinstance(data, list) else data.get("results", [])
        self.assertEqual(len(results), 0)

    def test_summary_is_get_only_and_live(self):
        client = APIClient()
        client.force_login(self.student)
        response = client.get("/api/attendance/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attendance_rate", response.json())

    @staticmethod
    def user_for(username):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.get(username=username)
