"""Daily log workflow tests (spec 19 - students & supervisors)."""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from core.testing import TestCaseBase
from logs.models import DailyLog


class DailyLogTests(TestCaseBase):
    def setUp(self):
        self.student_client = APIClient()
        self.student_client.force_login(self.student)
        self.supervisor_client = APIClient()
        self.supervisor_client.force_login(self.supervisor)
        self.other_supervisor_client = APIClient()
        self.other_supervisor_client.force_login(self.other_supervisor)

    def _valid_payload(self, day=None):
        return {
            "log_date": (day or date.today()).isoformat(),
            "activities": "Built and tested feature X.",
            "tools_used": "VS Code",
            "skills_learned": "Testing",
            "hours_spent": 4,
        }

    # ---------------------------------------------------------------- #
    # Students
    # ---------------------------------------------------------------- #
    def test_student_cannot_create_log(self):
        client = APIClient()
        client.force_login(self.student)
        response = client.post(
            "/api/logs/",
            {
                "log_date": date.today().isoformat(),
                "activities": "Built a login page for the organization website.",
                "tools_used": "HTML/CSS",
                "skills_learned": "Frontend basics",
                "hours_spent": 3.5,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "draft")

    def test_duplicate_log_date_rejected(self):
        response = self.student_client.post(
            "/api/logs/", self._valid_payload(), content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        log_id = response.json()["id"]
        duplicate = self.student_client.post(
            "/api/logs/", self._valid_payload(), content_type="application/json"
        )
        self.assertEqual(duplicate.status_code, 400)
        del log_id

    def test_future_log_date_rejected(self):
        response = self.student_client.post(
            "/api/logs/",
            self._valid_payload(day=date.today() + timedelta(days=2)),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("future", response.json()["log_date"][0])

    def test_empty_activities_rejected(self):
        payload = self._valid_payload()
        payload["activities"] = "   "
        response = self.student_client.post("/api/logs/", payload, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_submit_moves_log_to_submitted(self):
        response = self.student_client.post(
            "/api/logs/", self._valid_payload(), content_type="application/json"
        )
        log_id = response.json()["id"]
        submit = self.student_client.post(f"/api/logs/{log_id}/submit/")
        self.assertEqual(submit.json()["status"], DailyLog.STATUS_SUBMITTED)

    def test_approved_log_cannot_be_edited(self):
        response = self.student_client.post(
            "/api/logs/", self._valid_payload(), content_type="application/json"
        )
        log_id = response.json()["id"]
        self.student_client.post(f"/api/logs/{log_id}/submit/")
        self.supervisor_client.post(
            f"/api/logs/{log_id}/review/",
            {"decision": "approve", "comment": "Nice"},
            content_type="application/json",
        )
        edit = self.student_client.patch(
            f"/api/logs/{log_id}/",
            {"activities": "should not work"},
            content_type="application/json",
        )
        self.assertEqual(edit.status_code, 400)
        log = DailyLog.objects.get(pk=log_id)
        self.assertNotEqual(log.activities, "should not work")

    def test_student_cannot_edit_another_students_log(self):
        response = self.student_client.post(
            "/api/logs/", self._valid_payload(), content_type="application/json"
        )
        log_id = response.json()["id"]
        other = APIClient()
        other.force_login(self.student_other)
        edit = other.patch(
            f"/api/logs/{log_id}/", {"activities": "hax"}, content_type="application/json"
        )
        self.assertEqual(edit.status_code, 404)

    def test_rejected_log_can_be_resubmitted(self):
        response = self.student_client.post(
            "/api/logs/", self._valid_payload(), content_type="application/json"
        )
        log_id = response.json()["id"]
        self.student_client.post(f"/api/logs/{log_id}/submit/")
        self.supervisor_client.post(
            f"/api/logs/{log_id}/review/",
            {"decision": "reject", "comment": "Unclear."},
            content_type="application/json",
        )
        self.student_client.patch(
            f"/api/logs/{log_id}/",
            {"activities": "Clearer description"},
            content_type="application/json",
        )
        resubmit = self.student_client.post(f"/api/logs/{log_id}/submit/")
        self.assertEqual(DailyLog.objects.get(pk=log_id).status, DailyLog.STATUS_SUBMITTED)
        del resubmit

    # ---------------------------------------------------------------- #
    # Supervisors
    # ---------------------------------------------------------------- #
    def _placed_student_log(self):
        """student1 is placed under supervisor1 within the test setup."""
        from organizations.models import Organization
        from core.models import Placement, SIWESSession

        organization, _ = Organization.objects.get_or_create(name="Placement Test Org")
        session = SIWESSession.objects.create(
            name="Log Session", start_date=date.today(), end_date=date.today() + timedelta(days=90)
        )
        Placement.objects.create(
            student=self.student_profile,
            organization=organization,
            supervisor=self.supervisor_profile,
            siwes_session=session,
            is_active=True,
        )
        response = self.student_client.post(
            "/api/logs/", self._valid_payload(), content_type="application/json"
        )
        return response.json()["id"]

    def test_assigned_supervisor_can_review(self):
        log_id = self._placed_student_log()
        self.student_client.post(f"/api/logs/{log_id}/submit/")
        review = self.supervisor_client.post(
            f"/api/logs/{log_id}/review/",
            {"decision": "approve", "comment": "Excellent work."},
            content_type="application/json",
        )
        self.assertEqual(review.status_code, 200)
        log = DailyLog.objects.get(pk=log_id)
        self.assertEqual(log.status, DailyLog.STATUS_APPROVED)
        self.assertEqual(log.supervisor, self.supervisor_profile)
        self.assertIsNotNone(log.reviewed_at)

    def test_other_supervisor_cannot_review(self):
        log_id = self._placed_student_log()
        self.student_client.post(f"/api/logs/{log_id}/submit/")
        review = self.other_supervisor_client.post(
            f"/api/logs/{log_id}/review/",
            {"decision": "approve"},
            content_type="application/json",
        )
        self.assertEqual(review.status_code, 403)

    def test_student_cannot_review_own_log(self):
        log_id = self._placed_student_log()
        self.student_client.post(f"/api/logs/{log_id}/submit/")
        review = self.student_client.post(
            f"/api/logs/{log_id}/review/", {"decision": "approve"}, content_type="application/json"
        )
        self.assertEqual(review.status_code, 403)

    def test_rejection_requires_a_reason(self):
        log_id = self._placed_student_log()
        self.student_client.post(f"/api/logs/{log_id}/submit/")
        review = self.supervisor_client.post(
            f"/api/logs/{log_id}/review/", {"decision": "reject", "comment": " "},
            content_type="application/json",
        )
        self.assertEqual(review.status_code, 400)

    def test_unplaced_student_log_not_visible_to_supervisors(self):
        """Without a placement, no supervisor can see the student's drafts."""
        response = self.student_client.post(
            "/api/logs/", self._valid_payload(), content_type="application/json"
        )
        response = self.student_client.post(f"/api/logs/{response.json()['id']}/submit/")
        # supervisor1 has no placement for student1 in this test, so the
        # supervisor list must not include it:
        listing = self.supervisor_client.get("/api/logs/?status=submitted")
        ids = [l["id"] for l in self._all_supervisor_logs(listing)]
        self.assertNotIn(response.json()["id"], ids)

    @staticmethod
    def _all_supervisor_logs(listing):
        data = listing.json()
        return data if isinstance(data, list) else data.get("results", [])

    def test_model_rejects_future_date(self):
        log = DailyLog(
            log_date=date.today() + timedelta(days=5),
            activities="x",
        )
        with self.assertRaises(ValidationError):
            log.full_clean()
