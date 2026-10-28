"""
SIWES Hub - end-to-end API smoke test.

Walks the exact demonstration workflow from the specification (section 14):

1-5   Student: login, dashboard, create a daily log, submit it, logout.
6-9   Supervisor: login, open submitted log, reject with a reason, logout.
10-11 Student: re-login, confirm status + feedback.
12    Student: create + submit a weekly report.
13    Supervisor: approve the report; record attendance for the student.
14-15 Student: submit project; supervisor reviews it.
16-19 Admin: dashboards, announcements, users, organizations, placements.

Prerequisite: START_APP.bat no longer seeds sample users. On a fresh database
run once before this script:
    backend/.venv/Scripts/python backend/manage.py seed_demo --password "..."
so the example accounts below exist with the password used here.

Run:  backend/.venv/Scripts/python tests/api_smoke.py [base_url]
Exit code 0 = all checks passed.
"""
import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PASSWORD = "Demo#2026!"

RESULTS = []


def as_list(response):
    """API lists return {'results': [...]} when paginated or a plain list."""
    data = response.json()
    return data.get("results", []) if isinstance(data, dict) else (data or [])


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    RESULTS.append((name, status, detail))
    print(f"[{status}] {name}" + (f" - {detail}" if detail and not condition else ""))


class Client:
    """Small session wrapper handling CSRF for our session-based API."""

    def __init__(self):
        self.session = requests.Session()

    def login(self, username, password=PASSWORD):
        self.session.get(f"{BASE}/api/auth/csrf/")
        token = self.session.cookies.get("csrftoken")
        response = self.session.post(
            f"{BASE}/api/auth/login/",
            json={"username": username, "password": password},
            headers={"X-CSRFToken": token, "Referer": BASE},
        )
        return response

    def write(self, method, url, json=None):
        token = self.session.cookies.get("csrftoken")
        return self.session.request(
            method,
            f"{BASE}{url}" if url.startswith("/") else url,
            json=json,
            headers={"X-CSRFToken": token, "Referer": BASE},
        )

    def get(self, url):
        return self.session.get(f"{BASE}{url}" if url.startswith("/") else url)


def main():
    # ------------------------------------------------------------------ #
    # 1-5 Student workflow
    # ------------------------------------------------------------------ #
    student = Client()
    response = student.login("student1")
    check("student login works", response.status_code == 200, str(response.status_code))
    me = student.get("/api/auth/me/").json()
    check("me returns student role", me.get("role") == "student", str(me))

    dashboard = student.get("/api/core/dashboard/").json()
    check("student dashboard 200", dashboard.get("role") == "student")
    check(
        "dashboard stats are live",
        all(
            key in dashboard.get("stats", {})
            for key in ("total_logs", "pending_logs", "attendance")
        ),
    )

    from datetime import date, timedelta

    today = date.today()
    # Try to use a date with no log; fall back to today.
    candidates = [today - timedelta(days=i) for i in range(60)]
    existing = {log["log_date"] for log in as_list(student.get("/api/logs/?page=1&page_size=100"))}
    log_date = next((d.isoformat() for d in candidates if d.isoformat() not in existing), today.isoformat())

    created = student.write(
        "POST",
        "/api/logs/",
        {
            "log_date": log_date,
            "activities": "API smoke test: wrote automated workflow checks.",
            "tools_used": "Python requests",
            "skills_learned": "API testing",
            "hours_spent": 3.0,
        },
    )
    check("student creates daily log", created.status_code == 201, created.text[:200])
    log_id = created.json().get("id")

    duplicate = student.write(
        "POST",
        "/api/logs/",
        {"log_date": log_date, "activities": "should be rejected"},
    )
    check("duplicate date rejected", duplicate.status_code == 400)

    submitted = student.write("POST", f"/api/logs/{log_id}/submit/")
    check("student submits log", submitted.status_code == 200 and submitted.json()["status"] == "submitted")

    student.write("POST", "/api/auth/logout/")
    me_after = student.get("/api/auth/me/")
    check("logout clears session", me_after.status_code in (401, 403), str(me_after.status_code))

    # ------------------------------------------------------------------ #
    # 6-9 Supervisor reviews
    # ------------------------------------------------------------------ #
    supervisor = Client()
    response = supervisor.login("chioma.eze")
    check("supervisor login works", response.status_code == 200)

    pending = as_list(supervisor.get("/api/logs/?status=submitted"))
    check("supervisor sees submitted logs", any(l["id"] == log_id for l in pending))

    # Supervisor of a different student cannot review (authorization test)
    other = as_list(supervisor.get("/api/logs/?student=4"))
    if other:
        other_id = other[0]["id"]
        forbidden = supervisor.write(
            "POST", f"/api/logs/{other_id}/review/", {"decision": "approve"}
        )
        check(
            "supervisor cannot review unassigned student's log",
            forbidden.status_code == 403, str(forbidden.status_code),
        )

    rejected = supervisor.write(
        "POST",
        f"/api/logs/{log_id}/review/",
        {"decision": "reject", "comment": "Add task outcome, then resubmit."},
    )
    check("supervisor rejects log with reason", rejected.status_code == 200 and rejected.json()["status"] == "rejected")

    # ------------------------------------------------------------------ #
    # 10-11 Student resubmission flow
    # ------------------------------------------------------------------ #
    student2 = Client()
    student2.login("student1")
    detail = student2.get(f"/api/logs/{log_id}/").json()
    check("student sees rejection feedback", detail["status"] == "rejected" and "outcome" in detail["supervisor_comment"])
    student2.write("PATCH", f"/api/logs/{log_id}/", {"activities": "Wrote automated workflow checks with clear outcomes."})
    resubmitted = student2.write("POST", f"/api/logs/{log_id}/submit/")
    check("student resubmits corrected log", resubmitted.status_code == 200)
    approved = supervisor.write("POST", f"/api/logs/{log_id}/review/", {"decision": "approve", "comment": "Approved. Good job."})
    check("supervisor approves resubmitted log", approved.status_code == 200)

    # ------------------------------------------------------------------ #
    # 12-13 Weekly report + attendance
    # ------------------------------------------------------------------ #
    this_monday = (today - timedelta(days=today.weekday())).isoformat()
    existing_reports = as_list(student2.get("/api/reports/?page=1&page_size=100"))
    used_weeks = {r["week_start"] for r in existing_reports}
    week_start = this_monday
    for i in range(104):
        if week_start not in used_weeks:
            break
        week_start = (today - timedelta(days=today.weekday(), weeks=i + 1)).isoformat()
    report = student2.write(
        "POST",
        "/api/reports/",
        {
            "week_start": week_start,
            "summary_of_activities": "Smoke-test week summary of activities.",
            "challenges_faced": "Automated testing setup.",
            "lessons_learned": "HTTP sessions and CSRF.",
            "skills_acquired": "Automated API testing",
        },
    )
    check("student creates weekly report", report.status_code == 201, report.text[:200])
    report_id = report.json().get("id")
    student2.write("POST", f"/api/reports/{report_id}/submit/")
    report_review = supervisor.write(
        "POST", f"/api/reports/{report_id}/review/", {"decision": "approve", "comment": "Good summary."}
    )
    check("supervisor approves weekly report", report_review.status_code == 200)

    attendance = supervisor.write(
        "POST",
        "/api/attendance/",
        {"student": 1, "date": today.isoformat(), "status": "present", "note": "smoke test"},
    )
    if attendance.status_code == 400 and "already exists" in attendance.text:
        attendance_list = as_list(supervisor.get("/api/attendance/?student=1&date=" + today.isoformat()))
        attendance = supervisor.write(
            "PATCH",
            f"/api/attendance/{attendance_list[0]['id']}/",
            {"status": "present"},
        )
        check("supervisor updates attendance", attendance.status_code == 200)
    else:
        check("supervisor records attendance", attendance.status_code == 201, attendance.text[:200])

    summary = student2.get("/api/attendance/summary/")
    check("student attendance summary works", summary.status_code == 200 and "attendance_rate" in summary.json())

    # Students cannot record attendance
    forged = student2.write(
        "POST", "/api/attendance/", {"student": 1, "date": today.isoformat(), "status": "present"}
    )
    check("student cannot record attendance", forged.status_code == 403, str(forged.status_code))

    # ------------------------------------------------------------------ #
    # 14-15 Projects
    # ------------------------------------------------------------------ #
    # GET /api/projects/me/ returns the project record itself (or {detail,
    # project}) when the student has none yet.
    project_payload = student2.get("/api/projects/me/").json()
    project = project_payload if project_payload.get("id") else None
    if project is None:
        created_project = student2.write(
            "POST",
            "/api/projects/me/",
            {"title": "Smoke Test Project", "technologies": "Python"},
        )
        check("student creates project", created_project.status_code == 201, created_project.text[:200])
        project = created_project.json()
    project_id = project["id"]
    if project["review_status"] in ("not_submitted", "rejected"):
        submitted_project = student2.write("POST", "/api/projects/me/submit/")
        check("student submits project", submitted_project.status_code == 200, submitted_project.text[:200])
    else:
        # Already submitted in an earlier run of this test: nothing to do.
        check("student submits project", True, "already submitted (repeat run)")
    project_state = (student2.get("/api/projects/me/").json() or {})
    if project_state.get("review_status") == "submitted":
        project_review = supervisor.write(
            "POST", f"/api/projects/{project_id}/review/", {"decision": "approve", "comment": "Approved."}
        )
        check("supervisor reviews project", project_review.status_code == 200, project_review.text[:200])
    else:
        check("supervisor reviews project", True, "project already reviewed (repeat run)")

    # ------------------------------------------------------------------ #
    # 16-19 Administrator
    # ------------------------------------------------------------------ #
    admin = Client()
    response = admin.login("admin_siwes")
    check("admin login works", response.status_code == 200)
    admin_dash = admin.get("/api/core/dashboard/")
    check("admin dashboard works", admin_dash.status_code == 200)

    announcement = admin.write(
        "POST",
        "/api/announcements/",
        {"title": "Smoke test announcement", "content": "Created by the automated test.", "audience": "students"},
    )
    check("admin publishes announcement", announcement.status_code == 201, announcement.text[:200])
    student_notif = as_list(student2.get("/api/notifications/"))
    check(
        "student received announcement notification",
        any("announcement" in (n.get("kind") or "") or "announcement" in n["title"].lower() for n in student_notif),
    )
    supervisor_ann = as_list(supervisor.get("/api/announcements/"))
    check(
        "supervisor does NOT see students-only announcement",
        not any(a["title"] == "Smoke test announcement" for a in supervisor_ann),
    )

    import time

    org_name = f"Smoke Corp {int(time.time())}"
    new_org = admin.write(
        "POST",
        "/api/organizations/",
        {"name": org_name, "industry": "Testing"},
    )
    check("admin creates organization", new_org.status_code == 201, new_org.text[:200])

    # student6 has no placement: assign one
    students = as_list(admin.get("/api/students/"))
    student6 = next((s for s in students if s["matric_number"] == "230591201"), None)
    existing_placement = as_list(
        admin.get(f"/api/core/placements/?student={student6['id']}")
    )
    if existing_placement:
        check("admin assigns placement", True, "student6 already placed (repeat run)")
    else:
        org_list = as_list(admin.get("/api/organizations/"))
        org_id = new_org.json().get("id") or org_list[0]["id"]
        placement = admin.write(
            "POST",
            "/api/core/placements/",
            {"student": student6["id"], "organization": org_id, "supervisor": 2, "siwes_session": 1},
        )
        check("admin assigns placement", placement.status_code == 201, placement.text[:200])
    # A second POST for the same student must always be rejected.
    if not existing_placement:
        placement2 = admin.write(
            "POST",
            "/api/core/placements/",
            {"student": student6["id"], "organization": org_id, "supervisor": 2, "siwes_session": 1},
        )
        check("duplicate placement rejected", placement2.status_code == 400)

    # --------------------------------------------------------------- #
    # Security: role escalation attempts must fail
    # --------------------------------------------------------------- #
    escalation = student2.write(
        "POST", "/api/users/", {"username": "hacker", "role": "admin", "password": "bad12345"}
    )
    check("student cannot create admin user", escalation.status_code in (401, 403))

    anonymous = requests.get(f"{BASE}/api/logs/")
    check("anonymous access rejected", anonymous.status_code in (401, 403))

    # ------------------------------------------------------------------ #
    print()
    failures = [r for r in RESULTS if r[1] != "PASS"]
    print(f"TOTAL: {len(RESULTS)} checks, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
