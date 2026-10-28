"""Weekly report workflow tests."""
from datetime import date, timedelta

from rest_framework.test import APIClient

from core.testing import TestCaseBase


class WeeklyReportTests(TestCaseBase):
    def setUp(self):
        self.student_client = APIClient()
        self.student_client.force_login(self.student)

    def _monday(self, weeks_ago=0):
        today = date.today() - timedelta(weeks=weeks_ago)
        return today - timedelta(days=today.weekday())

    def _payload(self):
        monday = self._monday(52)  # far enough in the past to be unique
        return {
            "week_start": monday.isoformat(),
            "week_end": (monday + timedelta(days=6)).isoformat(),
            "summary_of_activities": "Worked on module A and module B.",
            "challenges_faced": "Learning curve.",
            "lessons_learned": "Planning matters.",
            "skills_acquired": "Django",
        }

    def test_report_starts_as_draft(self):
        response = self.student_client.post("/api/reports/", self._payload(), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "draft")

    def test_report_week_end_must_be_after_start(self):
        payload = self._payload()
        payload["week_end"] = payload["week_start"]
        response = self.student_client.post("/api/reports/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_future_week_rejected(self):
        payload = self._payload()
        payload["week_start"] = (date.today() + timedelta(days=10)).isoformat()
        response = self.student_client.post("/api/reports/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_duplicate_week_rejected(self):
        first = self.student_client.post("/api/reports/", self._payload(), content_type="application/json")
        self.assertEqual(first.status_code, 201)
        second = self.student_client.post("/api/reports/", self._payload(), content_type="application/json")
        self.assertEqual(second.status_code, 400)

    def test_student_cannot_see_other_students_reports(self):
        client = APIClient()
        client.force_login(self.student_other)
        listing = client.get("/api/reports/")
        data = listing.json()
        results = data if isinstance(data, list) else data.get("results", [])
        self.assertEqual(len(results), 0)
