"""Announcement visibility tests."""
from rest_framework.test import APIClient

from core.testing import TestCaseBase
from notifications.models import Notification


class AnnouncementTests(TestCaseBase):
    def _publish(self, audience):
        client = APIClient()
        client.force_login(self.admin)
        return client.post(
            "/api/announcements/",
            {"title": f"Test announcement {audience}", "content": "Test content.", "audience": audience},
            content_type="application/json",
        )

    def test_only_admin_can_publish(self):
        client = APIClient()
        client.force_login(self.supervisor)
        response = client.post(
            "/api/announcements/",
            {"title": "X", "content": "Y", "audience": "all"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_students_only_announcement_visible_to_students(self):
        self._publish("students")
        client = APIClient()
        client.force_login(self.student)
        listing = client.get("/api/announcements/")
        results = listing.json() if isinstance(listing.json(), list) else listing.json().get("results", [])
        self.assertTrue(any(a["audience"] == "students" for a in results))

    def test_students_only_announcement_hidden_from_supervisors(self):
        self._publish("students")
        client = APIClient()
        client.force_login(self.supervisor)
        listing = client.get("/api/announcements/")
        results = listing.json() if isinstance(listing.json(), list) else listing.json().get("results", [])
        self.assertFalse(any(a["audience"] == "students" for a in results))

    def test_mark_read_updates_state(self):
        self._publish("all")
        client = APIClient()
        client.force_login(self.student)
        listing = client.get("/api/announcements/")
        ann_id = listing.json()["results"][0]["id"] if isinstance(listing.json(), dict) else listing.json()[0]["id"]
        mark = client.post(f"/api/announcements/{ann_id}/read/")
        self.assertEqual(mark.status_code, 200)
        listing = client.get("/api/announcements/")
        data = listing.json()
        item = (data if isinstance(data, list) else data["results"])[0]
        self.assertTrue(item["read_by_me"])

    def test_announcement_creates_notifications_for_students(self):
        self._publish("students")
        notifications = Notification.objects.filter(recipient=self.student)
        self.assertTrue(notifications.exists())

    def test_admin_sees_everything(self):
        self._publish("students")
        self._publish("supervisors")
        client = APIClient()
        client.force_login(self.admin)
        listing = client.get("/api/announcements/")
        data = listing.json()
        results = data if isinstance(data, list) else data.get("results", [])
        self.assertEqual(len(results), 2)
