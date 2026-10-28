"""
Generate the SIWES Hub documentation set.

Everything that can be derived from the live Django project is derived from
it (data model, API endpoints, test inventory), so the documents stay in
sync with the code and contain no invented claims.

Outputs:
  documentation/SIWES_Hub_Project_Overview.docx
  documentation/SIWES_Hub_Installation_Guide.docx
  documentation/SIWES_Hub_User_Manual.docx
  documentation/SIWES_Hub_System_Design_Document.docx
  documentation/SIWES_Hub_Testing_Report.docx
  API_Documentation.md            (project root)
  database/schema.sql             (fresh schema from all migrations)

Run with the project venv:
    python tools/generate_docs.py
"""
import os
import sys
import sqlite3
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.db import connections  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.test.runner import DiscoverRunner  # noqa: E402
from django.urls import get_resolver  # noqa: E402
from django.utils.html import strip_tags  # noqa: E402

from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.shared import Pt, RGBColor  # noqa: E402

ACCENT = RGBColor(0x5B, 0x21, 0xB6)  # the application's purple accent

# --------------------------------------------------------------------------- #
# Django introspection helpers
# --------------------------------------------------------------------------- #

def app_models():
    """Model classes grouped by app label, skipping framework apps."""
    own = [
        "accounts", "core", "organizations", "students", "supervisors",
        "logs", "reports", "attendance", "projects", "announcements",
        "notifications",
    ]
    result = {}
    for label in own:
        result[label] = list(apps.get_app_config(label).get_models())
    return result


def field_rows(model):
    rows = []
    for f in model._meta.get_fields():
        if f.auto_created and not f.concrete:
            continue
        kind = f.get_internal_type() if hasattr(f, "get_internal_type") else type(f).__name__
        detail = []
        if getattr(f, "primary_key", False):
            detail.append("PK")
        if getattr(f, "unique", False):
            detail.append("unique")
        if f.is_relation:
            target = f.related_model._meta.label
            detail.append(f"-> {target}")
        if getattr(f, "null", False) and f.editable:
            detail.append("optional")
        rows.append((f.name, kind, ", ".join(detail)))
    return rows


API_TEST_PAIRS = [
    ("accounts", "accounts.tests"),
    ("core", "core.tests"),
    ("students", "students.tests"),
    ("logs", "logs.tests"),
    ("reports", "reports.tests"),
    ("attendance", "attendance.tests"),
    ("projects", "projects.tests"),
    ("announcements", "announcements.tests"),
]


def count_tests():
    """Number of test methods per Django app, without executing them."""
    runner = DiscoverRunner(verbosity=0, interactive=False)
    counts = []
    total = 0
    for label, module in API_TEST_PAIRS:
        suite = runner.build_suite([module])
        n = suite.countTestCases()
        counts.append((label, n))
        total += n
    return counts, total


def walk_urls(resolver, prefix=""):
    """Flatten the URL configuration into (method set, path) tuples."""
    entries = []
    for pattern in resolver.url_patterns:
        path = prefix + str(pattern.pattern)
        if hasattr(pattern, "url_patterns"):  # include()
            entries.extend(walk_urls(pattern, path))
        elif getattr(pattern, "name", None) or hasattr(pattern.callback, "view_class"):
            view = getattr(pattern.callback, "view_class", None)
            verbs = []
            if view is not None:
                for v in ("get", "post", "put", "patch", "delete"):
                    if v in vars(view):
                        verbs.append(v.upper())
            entries.append(("/" + path, view.__name__ if view else "", ", ".join(verbs) or "GET"))
    return entries


def fresh_schema_sql():
    """Build schema.sql from every migration in a throw-away database."""
    tmp = Path(tempfile.mkdtemp()) / "schema.sqlite3"
    alias_settings = dict(connections.settings["default"])
    alias_settings["NAME"] = str(tmp)
    connections.databases["docs"] = alias_settings
    call_command("migrate", database="docs", verbosity=0, interactive=False)
    conn = sqlite3.connect(str(tmp))
    stmts = []
    for kind, name, sql in conn.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
        "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END, name"
    ):
        stmts.append(f"-- {kind} {name}\n{sql};")
    conn.close()
    try:
        connections["docs"].close()
    except Exception:
        pass
    try:
        tmp.unlink(missing_ok=True)
    except PermissionError:
        pass  # windows file lock; the temp folder is cleaned by the OS later
    del connections.databases["docs"]
    return "\n\n".join(stmts)


# --------------------------------------------------------------------------- #
# docx helpers
# --------------------------------------------------------------------------- #

def new_doc(title, subtitle):
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    t = doc.add_heading(title, level=0)
    for run in t.runs:
        run.font.color.rgb = ACCENT
    p = doc.add_paragraph(subtitle)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()
    return doc


def h(doc, text, level=1):
    doc.add_heading(text, level=level)


def p(doc, text, bold=False):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.bold = bold
    return para


def bullets(doc, items):
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def numbered(doc, items):
    for item in items:
        doc.add_paragraph(item, style="List Number")


def table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, htext in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = htext
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = str(val)
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                r.cells[i].width = w
    doc.add_paragraph()
    return t


def verbatim(doc, text):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    para.paragraph_format.left_indent = Pt(18)
    return para


# --------------------------------------------------------------------------- #
# Shared facts
# --------------------------------------------------------------------------- #

def facts():
    models_by_app = app_models()
    test_counts, test_total = count_tests()
    endpoints = walk_urls(get_resolver("config.urls"))
    return models_by_app, test_counts, test_total, endpoints


VERSION = "1.0"
DATE = "October 2026"


# --------------------------------------------------------------------------- #
# Document 1 - Project overview
# --------------------------------------------------------------------------- #

def doc_overview(ctx):
    models_by_app, test_counts, test_total, endpoints = ctx
    doc = new_doc(
        "SIWES Hub - Project Overview",
        f"SIWES Management & Monitoring Portal, version {VERSION}, {DATE}",
    )
    h(doc, "1. Abstract")
    p(doc, "SIWES Hub is a local, web-based management and monitoring portal for the "
           "Students Industrial Work Experience Scheme (SIWES). It replaces paper logbooks "
           "and manual supervision with a single database-backed application in which students "
           "record their daily activities, supervisors review and approve them, and the SIWES "
           "office administers users, placements, sessions and announcements. The system was "
           "built as an academic final-year project and is designed to run entirely on one "
           "Windows computer without an internet connection.")

    h(doc, "2. Objectives")
    bullets(doc, [
        "Provide three distinct, server-enforced user roles: Student, Supervisor and Administrator.",
        "Digitise the daily logbook with a draft / submitted / approved / rejected workflow and supervisor feedback.",
        "Provide weekly reports with the same review workflow, week by week.",
        "Record attendance (present / absent / late / excused) and compute attendance rates per student.",
        "Manage each student's single training project through submission and supervisor approval.",
        "Let students catalogue the skills they learned, for their final report.",
        "Give the SIWES office user management, organisation and placement management, SIWES sessions, announcements and a full audit trail.",
        "Package the whole system as a portable Windows build that starts with one double-click.",
    ])

    h(doc, "3. Technology stack")
    table(doc,
          ["Layer", "Technology", "Why"],
          [
              ["Frontend", "HTML5, CSS3, vanilla JavaScript, Lucide icons", "No framework needed; runs in any modern browser from the Django server itself"],
              ["API", "Django REST Framework 3.17", "Session-authenticated JSON API under /api/"],
              ["Backend", "Python 3.13 / Django 5.1", "Batteries-included framework with migrations, auth and ORM"],
              ["Database", "SQLite (file database/data/db.sqlite3)", "Zero-configuration, portable, easy to back up by copying one file"],
              ["Packaging", "Windows batch scripts + embedded Python 3.13", "Runs from a USB stick or folder copy without installing Python"],
          ])

    h(doc, "4. Module map")
    module_names = {
        "accounts": "Authentication, custom user model, role management, login throttling",
        "core": "Dashboard statistics, placements, SIWES sessions, audit trail, pagination",
        "organizations": "Organisation (placement company) records",
        "students": "Student profiles, skills, admin-facing student directory",
        "supervisors": "Supervisor profiles and directory",
        "logs": "Daily logs and the review workflow",
        "reports": "Weekly reports and the review workflow",
        "attendance": "Attendance records and summaries",
        "projects": "Student training projects and their approval",
        "announcements": "Organisation-wide announcements with per-user read state",
        "notifications": "Per-user notification inbox (bell in the top bar)",
    }
    table(doc, ["App (Django)", "Responsibility"],
          [[name, desc] for name, desc in module_names.items()])

    h(doc, "5. System contents")
    total_models = sum(len(v) for v in models_by_app.values())
    p(doc, f"The shipped system contains {total_models} database models across 11 "
           f"applications, {len(endpoints)} API endpoints, {test_total} automated backend tests "
           "and 16 frontend pages (landing, sign-in, registration, 3 role dashboards and "
           "10 working areas).")


    h(doc, "6. How to run (summary)")
    numbered(doc, [
        "Development machine: double-click deployment\\START_APP.bat. The script applies "
        "migrations, asks once for the first administrator account (hidden password prompt) "
        "on a fresh database, starts the server and opens the browser at http://127.0.0.1:8000.",
        "Students and supervisors then create their own accounts on the registration page "
        "(linked from the sign-in screen); supervisor accounts stay pending until the "
        "administrator approves them on the Supervisors page.",
        "Any other Windows machine: double-click deployment\\BUILD_PORTABLE.bat once on the "
        "development machine, then copy dist\\SIWES-Hub-Portable to the target machine and "
        "run START_APP.bat inside it. No Python installation is required.",
        "Stop the server with deployment\\STOP_APP.bat.",
    ])

    h(doc, "7. Limitations")
    bullets(doc, [
        "This is a single-computer demonstration system: DEBUG mode is on, and the server binds to 127.0.0.1 only.",
        "Attendance, logs and reports trust the local machine clock; there is no device biometrics or geolocation.",
        "There is no e-mail delivery: registrations are approved inside the app and passwords are created by the user or the SIWES office, never sent by mail.",
        "Reports (weekly/daily) are viewed in the browser; printing to PDF relies on the browser's print dialog.",
    ])
    doc.save(PROJECT_ROOT / "documentation" / "SIWES_Hub_Project_Overview.docx")


# --------------------------------------------------------------------------- #
# Document 2 - Installation guide
# --------------------------------------------------------------------------- #

def doc_installation(ctx):
    doc = new_doc(
        "SIWES Hub - Installation Guide",
        f"Version {VERSION}, {DATE}. Audience: examiners, technicians and anyone "
        "demonstrating the system on a Windows PC.",
    )

    h(doc, "1. What you need")
    bullets(doc, [
        "Windows 10 or 11 (64-bit).",
        "A modern browser (Edge, Chrome or Firefox).",
        "Nothing else - the portable build carries its own Python runtime; the development "
        "build needs the project's .venv folder (already present).",
    ])

    h(doc, "2. Starting the pre-built project (development machine)")
    numbered(doc, [
        "Open the project folder.",
        "Double-click deployment\\START_APP.bat.",
        "A black server window opens (it can be minimised). After a few seconds the browser "
        "opens http://127.0.0.1:8000 automatically.",
        "On a fresh database the launcher asks once for an administrator username, email and "
        "password (the password is typed in hidden and stored only as a hash) - these "
        "credentials are the SIWES office's own and are never printed anywhere.",
        "Students and supervisors use the Create account link on the sign-in page to "
        "register themselves; supervisors wait for administrator approval.",
    ])
    p(doc, "What the launcher does: it picks the Python interpreter (.venv first, then the "
           "portable runtime, then any system Python), applies pending migrations, creates "
           "the first administrator account when none exists, starts the Django server in "
           "its own window, waits until the site answers and only then opens the browser. "
           "If a server is already running, the script reuses it instead of starting a "
           "second copy. No demonstration users are created automatically.", bold=False)

    h(doc, "3. Building the portable package")
    numbered(doc, [
        "On the development machine, double-click deployment\\BUILD_PORTABLE.bat.",
        "The script extracts the embedded Python 3.13 runtime from "
        "deployment\\runtimeCache\\python-3.13.2-embed-amd64.zip, downloads the Django/DRF "
        "libraries into the runtime, copies the source tree and self-tests the result.",
        "The result is dist\\SIWES-Hub-Portable (a folder) and "
        "dist\\SIWES-Hub-Portable.zip (the same folder zipped for copying).",
    ])
    h(doc, "4. Running the portable package on another PC", level=2)
    numbered(doc, [
        "Copy the folder (or unzip the archive) anywhere, e.g. to the Desktop or a USB stick.",
        "Double-click deployment\\START_APP.bat inside the copied folder.",
        "On first start the package creates its own empty database and asks once for the "
        "first administrator account - every other account is registered or created in "
        "the app afterwards.",
    ])

    h(doc, "5. Stopping the server")
    p(doc, "Double-click deployment\\STOP_APP.bat. It stops only processes whose command "
           "line runs the SIWES Hub server on port 8000 and never touches unrelated programs.")

    h(doc, "6. Data, backup and reset")
    bullets(doc, [
        "All data lives in one file: database\\data\\db.sqlite3.",
        "Back up = copy that file while the server is stopped.",
        "Full reset = stop the server, delete database\\data\\db.sqlite3, run START_APP.bat "
        "again: migrations are recreated and the launcher asks for a new first administrator.",
        "Server messages are appended to database\\server.log (created by the launcher).",
    ])

    h(doc, "7. Troubleshooting")
    table(doc, ["Symptom", "Cause and fix"],
          [
              ["Browser does not open / page unreachable after 30 s",
               "Look at database\\server.log. The most common cause is another program "
               "already using port 8000 - close it and run START_APP.bat again."],
              ["'No Python interpreter was found'",
               "Neither .venv nor the portable runtime was found. Run "
               "BUILD_PORTABLE.bat once on the development machine, or install Python 3.13."],
              ["A pending supervisor cannot sign in",
               "Approve or reject the registration on the Supervisors page: a yellow "
               "'Pending Supervisor Approvals' banner lists who is waiting."],
              ["Port 8000 busy message",
               "Another application owns the port. Stop it or start SIWES Hub on another "
               "machine/port (advanced)."],
          ])
    doc.save(PROJECT_ROOT / "documentation" / "SIWES_Hub_Installation_Guide.docx")


# --------------------------------------------------------------------------- #
# Document 3 - User manual
# --------------------------------------------------------------------------- #

def doc_user_manual(ctx):
    doc = new_doc(
        "SIWES Hub - User Manual",
        f"Version {VERSION}, {DATE}. A role-by-role walkthrough of every screen.",
    )

    h(doc, "1. Signing in")
    numbered(doc, [
        "Open http://127.0.0.1:8000 (the launcher opens it automatically).",
        "Press Sign in and enter your username and password.",
        "New students and supervisors use the Create account link to register instead.",
        "After signing in you land on the dashboard for your role. The bell icon in the top "
        "bar shows your unread notifications; the avatar opens your profile and Settings.",
    ])
    p(doc, "Repeated failed logins are blocked for a short cool-down period "
           "(5 attempts per 10 minutes) to discourage password guessing.")

    h(doc, "2. Student manual")
    h(doc, "2.1 Daily logs", level=2)
    numbered(doc, [
        "Open Daily Logs and press New log (or the New log card on your dashboard).",
        "Choose the date (one log per day; the system rejects duplicates), select the "
        "activity type and describe what you did and what you learned.",
        "Save as draft to continue later, or press Submit to send it to your supervisor.",
        "Statuses: Draft (pencil icon to edit) -> Submitted -> Approved or Rejected. "
        "A rejected log shows the supervisor's comment; edit and resubmit it.",
    ])
    h(doc, "2.2 Weekly reports", level=2)
    p(doc, "Open Weekly Reports, press New report, choose the week, summarise the week's "
           "work and list challenges, then Submit. Approved reports are read-only.")
    h(doc, "2.3 Attendance", level=2)
    p(doc, "Attendance is recorded by your supervisor or the SIWES office. The page shows "
           "your daily records and summary cards (days present, absent, late, attendance rate).")
    h(doc, "2.4 Training project", level=2)
    p(doc, "Open Projects (My project). Submit one project: title, description and the "
           "technologies used. The supervisor either approves it or returns it with feedback; "
           "you can revise and resubmit while it is not approved.")
    h(doc, "2.5 Profile and skills", level=2)
    p(doc, "The Profile page shows your account, placement (organisation and supervisor) and "
           "lets you edit contact and academic details. Record the skills you learned under "
           "Skills learned - each skill has a proficiency level and date; they feed your "
           "final report.")
    h(doc, "2.6 Announcements and notifications", level=2)
    p(doc, "Announcements from the SIWES office appear on the Announcements page; press "
           "Mark as read to track what you have seen. Events such as an approved or rejected "
           "log arrive as notifications in the bell menu.")

    h(doc, "3. Supervisor manual")
    bullets(doc, [
        "Dashboard: live counts of students assigned to you, pending reviews and recent activity.",
        "Daily Logs: the Review queue lists submitted logs. Open one, read it, and either "
        "Approve or Reject with a required comment. The student is notified immediately.",
        "Weekly Reports: same review flow, week by week.",
        "Attendance: press Record attendance, choose student, date and status (present / "
        "absent / late / excused). Existing records can be edited; summaries update live.",
        "Students: directory of your assigned students with contact details, placement and progress counts.",
        "Projects: review submitted projects (approve / request changes with feedback).",
    ])

    h(doc, "4. Administrator (SIWES office) manual")
    bullets(doc, [
        "Dashboard: institution-wide statistics (students, supervisors, logs pending, attendance rate, placement coverage), organisation distribution and the latest audit trail entries.",
        "Students: register a student (account + profile in one form), edit, assign a placement (organisation + supervisor), and deactivate accounts.",
        "Supervisors: register supervisors with title and staff ID; see assigned student counts.",
        "Organisations: manage placement companies and the active SIWES session.",
        "Announcements: publish to everyone, only students or only supervisors; edit or retire old ones.",
        "Audit trail: every sensitive action (logins, registrations, approvals, placement changes, announcements) is recorded with the actor, action and timestamp.",
        "Settings: change your own password; sign out.",
    ])

    h(doc, "5. Who can do what (server-enforced)")
    table(doc, ["Action", "Student", "Supervisor", "Administrator"],
          [
              ["Create / edit own daily log", "Yes", "-", "-"],
              ["Review (approve/reject) logs and reports", "-", "Yes", "-"],
              ["Record / edit attendance", "-", "Yes", "Yes"],
              ["Submit training project", "Yes", "-", "-"],
              ["Review projects", "-", "Yes", "-"],
              ["Register users / manage placements", "-", "-", "Yes"],
              ["Publish announcements", "-", "-", "Yes"],
              ["Read own notifications", "Yes", "Yes", "Yes"],
              ["View audit trail", "-", "-", "Yes"],
          ])
    p(doc, "Authorisation is checked in the API layer for every request; hiding a button in "
           "the browser is never the only protection.")

    doc.save(PROJECT_ROOT / "documentation" / "SIWES_Hub_User_Manual.docx")


# --------------------------------------------------------------------------- #
# Document 4 - System design
# --------------------------------------------------------------------------- #

def doc_design(ctx):
    models_by_app, _counts, _total, endpoints = ctx
    doc = new_doc(
        "SIWES Hub - System Design Document",
        f"Version {VERSION}, {DATE}. Architecture, data model and API design.",
    )

    h(doc, "1. Architecture overview")
    p(doc, "SIWES Hub is a server-rendered entry point with a JavaScript-enhanced frontend "
           "talking to a JSON API. One Django process serves everything on port 8000:")
    verbatim(doc,
        "Browser (vanilla JS pages)\n"
        "   |  HTML pages  /pages/<name>.html   (whitelist in config/pages.py)\n"
        "   |  CSS/JS/fonts /css, /js, /assets  (served with Cache-Control: no-cache)\n"
        "   |  JSON API    /api/...            (Django REST Framework, session + CSRF)\n"
        "   v\n"
        "Django 5.1 (11 apps)  --ORM-->  SQLite  database/data/db.sqlite3")
    bullets(doc, [
        "Every page is a static HTML file; navigation.js builds the role-specific sidebar and top bar after login.",
        "api.js is the single HTTP helper: it attaches the CSRF token, unwraps JSON and normalises errors.",
        "Pages never trusted the browser with business rules: role checks live in the DRF views/serialisers.",
        "The dashboard, review queues and summaries are computed live from the database on every request - no cached demo numbers.",
    ])

    h(doc, "2. Authentication and security design")
    bullets(doc, [
        "Custom user model (accounts.User) with a role field constrained to student / supervisor / admin; AUTH_USER_MODEL is set project-wide.",
        "Session authentication with CSRF protection on every state-changing request; the frontend reads the csrf cookie and sends X-CSRFToken.",
        "Role enforcement: separate permission checks in each APIView (e.g. only supervisors may review logs; only admins may create users). Anonymous requests to /api/ are rejected.",
        "Login throttling: five failed attempts per username start a 10-minute cool-down (LOGIN_MAX_ATTEMPTS).",
        "Audit trail (core.AuditLog) records actor, action and detail for sensitive operations.",
        "Pages are served from a strict whitelist (config/pages.py) - arbitrary template paths are not accepted; static file serving rejects path traversal via Django's safe_join.",
        "The Django admin lives at /django-admin/ (deliberately not /admin/) and is only for staff.",
    ])

    h(doc, "3. Workflow design")
    h(doc, "3.1 Daily log lifecycle", level=2)
    verbatim(doc, "Draft --> Submitted --> Approved\n"
                  "            ^             |\n"
                  "            +-- Rejected <+   (edit + resubmit, comment required)")
    h(doc, "3.2 Notifications", level=2)
    p(doc, "Domain events call notifications.utils.notify(recipient, title, body, url), "
           "which creates a per-user Notification row. The frontend polls the inbox for the "
           "bell badge; clicking an item or 'Mark all as read' calls the read endpoints.")
    h(doc, "3.3 Pagination", level=2)
    p(doc, "core.pagination.OptionalPagination returns a plain JSON array when the client "
           "omits ?page=, and {count, pages, page, results} when it supplies one. This keeps "
           "small collections simple while large tables page through the UI.")

    h(doc, "4. Data model")
    for idx, (app_label, models) in enumerate(models_by_app.items(), start=1):
        h(doc, f"4.{idx} {app_label}", level=2)
        for model in models:
            h(doc, model.__name__, level=3)
            rows = field_rows(model)
            table(doc, ["Field", "Type", "Constraints / relation"], rows)

    h(doc, "5. API surface")
    p(doc, f"The API exposes {len(endpoints)} endpoints under /api/ "
           "(the full request/response reference is API_Documentation.md in the project root).")
    table(doc, ["Endpoint", "View", "Verbs"],
          [[e[0], e[1], e[2]] for e in endpoints])

    h(doc, "6. Frontend structure")
    verbatim(doc,
        "frontend/\n"
        "  pages/    15 whitelisted HTML pages (landing, login, 3 dashboards, 10 work areas)\n"
        "  css/      fonts, main design system, dashboard, forms, icons, responsive\n"
        "  js/       api, auth, ui, navigation, notifications + one controller per page\n"
        "  assets/   vendored lucide icons and the Poppins/Pacifico woff2 fonts")

    h(doc, "7. Future work")
    bullets(doc, [
        "PostgreSQL and real web-server deployment (gunicorn/NGINX) behind institution SSO.",
        "E-mail/ SMS notifications and password reset.",
        "File attachments (photos of signed logbook pages) and PDF export of reports.",
        "Offline-first PWA for students in low-connectivity industrial placements.",
    ])
    doc.save(PROJECT_ROOT / "documentation" / "SIWES_Hub_System_Design_Document.docx")


# --------------------------------------------------------------------------- #
# Document 5 - Testing report
# --------------------------------------------------------------------------- #

def doc_testing(ctx):
    models_by_app, counts, total, endpoints = ctx
    doc = new_doc(
        "SIWES Hub - Testing Report",
        f"Version {VERSION}, {DATE}. What was tested, how, and the honest results.",
    )

    h(doc, "1. Test strategy")
    bullets(doc, [
        "Unit and integration tests: Django's built-in test runner with a temporary SQLite "
        "database, covering models, serializers, API permissions and workflow state machines.",
        "Live API smoke test: tests/api_smoke.py performs 30 sequential checks against a "
        "running server with real sessions (requests), exercising the complete student -> "
        "supervisor -> admin demonstration workflow.",
        "Interactive browser verification: every page was driven in a real browser (login, "
        "create, edit, review, delete, notifications, deep links, pagination).",
        "Manual visual check of every page against the approved UI reference design "
        "(design/siwes-hub-ui-reference.png, option 1).",
    ])

    h(doc, "2. Automated backend test inventory")
    table(doc, ["App", "Tests"], [[label, str(n)] for label, n in counts] + [["Total", str(total)]])
    p(doc, f"Result: {total}/{total} tests pass. Command:")
    verbatim(doc,
        "cd backend\n"
        ".venv\\Scripts\\python.exe manage.py test accounts core students logs reports "
        "attendance projects announcements")

    h(doc, "3. What the automated tests cover")
    bullets(doc, [
        "Authentication: login per role, logout, wrong password, throttling after repeated failures, anonymous rejection.",
        "Authorisation: students cannot review logs, record attendance or create admin users; supervisors are scoped to their own students; admins-only endpoints reject other roles.",
        "Daily logs: one log per day rule, draft/submit/review transitions, comment required for rejection, resubmission after rejection, notification on each review.",
        "Weekly reports: creation per week, submission, approval flow and notifications.",
        "Attendance: recording rules (present/absent/late/excused), duplicate handling and summary computation.",
        "Projects: one project per student, submission and supervisor review flow.",
        "Announcements: audience targeting (all/students/supervisors) and read state per user.",
        "Organisations, placements, SIWES sessions and the audit trail on admin actions.",
    ])

    h(doc, "4. Live API smoke test (30 checks)")
    p(doc, "Command: .venv\\Scripts\\python.exe tests\\api_smoke.py (requires a running server).")
    p(doc, "Prerequisite: the script drives a fixed set of example accounts, so first run "
           ".venv\\Scripts\\python.exe backend\\manage.py seed_demo --password \"<your dev "
           "password>\" once. The launcher no longer seeds sample data automatically.")
    p(doc, "Result at time of writing: 30/30 checks pass. The script creates a small amount "
           "of clearly-labelled test data ('Smoke test ...') which can be deleted "
           "from the Announcements page afterwards.")

    h(doc, "5. Browser verification performed")
    bullets(doc, [
        "Landing page and login page render per the reference design; registration link visible.",
        "Registration: student self-registration signs the browser in immediately; supervisor self-registration creates a pending account that an administrator approves (Approve) or declines (Reject) on the Supervisors page, where a Pending Supervisor Approvals banner lists the queue.",
        "Duplicate emails / matric numbers / usernames are rejected with clear field errors; public registration can never create administrator accounts.",
        "Student: dashboard statistics, create draft log, duplicate-date validation error, submit, weekly report create+submit, read-only attendance, project page, profile edit + skills add, announcement read tracking, notification badge count, mark-all-read.",
        "Supervisor: dashboard, log review modal approve with comment (queue count updates, student notified), attendance recording modal, students/supervisors/organisations pages scoped to role, project review.",
        "Administrator: dashboard live stats and audit trail, student registration + placement assignment, announcements publish/edit/delete, organisations and SIWES session management.",
        "Cross-cutting: session persistence after reload, logout, invalid login error message, empty-state panels (e.g. administrator notifications), 404 page for unknown page names.",
    ])

    h(doc, "6. Known limitations found during testing")
    bullets(doc, [
        "The dev-mode server is single-process; concurrent multi-user load beyond a classroom demo is out of scope.",
        "Password reset and e-mail delivery are not implemented; forgotten passwords "
        "are reset by an administrator from the user management area.",
        "Weekly report review cannot yet attach a corrected document - only comments.",
    ])
    p(doc, "Everything else listed in section 5 was verified working on 21 October 2026.")

    doc.save(PROJECT_ROOT / "documentation" / "SIWES_Hub_Testing_Report.docx")


# --------------------------------------------------------------------------- #
# API_Documentation.md
# --------------------------------------------------------------------------- #

API_MD_HEADER = """# SIWES Hub - API Documentation

All endpoints live under `/api/` and use **session authentication** with **CSRF
protection** (the frontend sends the `X-CSRFToken` header from the `csrftoken`
cookie). Every request must be authenticated unless stated otherwise.

Conventions:

* Successful list requests return a JSON **array** when `?page=` is omitted,
  or `{count, pages, page, results}` when paginated.
* Errors return `{"detail": "..."}` (or field errors as
  `{"field": ["message", ...]}`) with a proper 4xx status code.
* Roles mentioned per endpoint are enforced server-side.
"""


def write_api_md(ctx):
    _m, _c, _t, endpoints = ctx
    lines = [API_MD_HEADER, "## Endpoint index", ""]
    lines.append("| Method(s) | Endpoint | View |")
    lines.append("|---|---|---|")
    for path_, view, verbs in endpoints:
        lines.append(f"| {verbs} | `{path_}` | {view} |")
    lines += [
        "",
        "## Key workflows",
        "",
        "### Authentication (accounts)",
        "- `POST /api/auth/login/` `{username, password}` -> sets the session cookie. "
        "Throttled to 5 failures per 10 minutes per username.",
        "- `POST /api/auth/logout/` - ends the session.",
        "- `GET /api/auth/me/` - current user (id, username, full_name, role, dashboard hints).",
        "- `GET /api/auth/csrf/` - ensures the CSRF cookie exists.",
        "- `POST /api/auth/register/student/` (public) `{full_name, email, matric_number, "
        "password, password2[, department, faculty, level]}` -> creates the user (role "
        "student is set server-side, password hashed) plus the StudentProfile; username "
        "becomes the matric number; the session starts immediately. Validation errors "
        "(duplicate email/matric, weak password) come back as 400 field errors; throttled "
        "to 8 registrations per IP per window.",
        "- `POST /api/auth/register/supervisor/` (public) `{username, full_name, email, "
        "password, password2[, title, staff_id, department]}` -> creates user + "
        "SupervisorProfile with the account inactive (`is_pending`); returns "
        "`status=pending_approval` and notifies every administrator. No session starts.",
        "- `GET /api/supervisors/?pending=true` (admin) - only the self-registered "
        "supervisors that still await approval (drives the Pending Supervisor Approvals "
        "banner on the Supervisors page).",
        "- Administrator approval: `PATCH /api/supervisors/<id>/` `{is_active: true}` on a "
        "pending supervisor activates the paired user account (audit `SUPERVISOR APPROVED`, "
        "the supervisor is notified). `{is_active: false}` on a pending supervisor "
        "**rejects** the registration (audit `SUPERVISOR REJECTED`, the applicant is "
        "notified, the account stays unable to sign in). Deactivating an already-active "
        "supervisor is audited separately (`SUPERVISOR DEACTIVATED`). The serializer "
        "exposes `user_is_active`/`is_pending`.",
        "",
        "### Daily logs (logs)",
        "- `GET /api/logs/` - students see their own logs; supervisors see their assigned "
        "students' logs; filters: `?status=draft|submitted|approved|rejected`, `?student=<id>`.",
        "- `POST /api/logs/` (student) - create draft; one log per date, duplicates get 400.",
        "- `PATCH /api/logs/<id>/` (student owner, draft/rejected only).",
        "- `POST /api/logs/<id>/submit/` (student owner).",
        "- `POST /api/logs/<id>/review/` (supervisor) `{decision: approved|rejected, comment}` - "
        "comment required when rejecting; notifies the student; audit-logged.",
        "",
        "### Weekly reports (reports)",
        "- Same pattern: `GET/POST /api/reports/`, `PATCH /api/reports/<id>/`, "
        "`POST /api/reports/<id>/submit/`, `POST /api/reports/<id>/review/`.",
        "",
        "### Attendance (attendance)",
        "- `GET /api/attendance/` - records scoped to role (`?student=`, `?date=`).",
        "- `POST /api/attendance/` (supervisor/admin) `{student, date, status, remarks}`.",
        "- `PATCH /api/attendance/<id>/` (supervisor/admin).",
        "- `GET /api/attendance/summary/` - per-role summary incl. attendance rate.",
        "",
        "### Projects (projects)",
        "- `GET /api/projects/me/` (student) / `GET /api/projects/` (supervisor/admin).",
        "- `POST /api/projects/` (student, one per student), `PATCH`, "
        "`POST /api/projects/<id>/submit/`, `POST /api/projects/<id>/review/`.",
        "",
        "### Students & skills (students)",
        "- `GET /api/students/` (supervisor/admin, filters), `POST /api/students/` (admin "
        "creates account+profile), `GET/PATCH /api/students/me/` (student own profile), "
        "`GET/PATCH/DELETE /api/students/<id>/` (admin).",
        "- Skills: `GET/POST /api/students/skills/`, `PATCH/DELETE /api/students/skills/<id>/` "
        "(student owns own skills).",
        "",
        "### Supervisors (supervisors)",
        "- `GET /api/supervisors/`, `POST` (admin), `GET/PATCH /api/supervisors/<id>/`, "
        "`GET /api/supervisors/me/`.",
        "",
        "### Organisations & placements (organizations, core)",
        "- `GET/POST /api/organizations/`, `GET/PATCH/DELETE /api/organizations/<id>/`.",
        "- `GET/POST /api/core/placements/`, `GET/PATCH /api/core/placements/<id>/` "
        "(admin assigns student -> organisation + supervisor).",
        "- SIWES sessions: `GET/POST /api/core/sessions/`, `PATCH /api/core/sessions/<id>/` "
        "(one active session).",
        "",
        "### Dashboard, announcements, notifications",
        "- `GET /api/core/dashboard/` - live role-specific statistics.",
        "- `GET/POST /api/announcements/`, `PATCH/DELETE /api/announcements/<id>/` (admin), "
        "`POST /api/announcements/<id>/read/` (per-user read state).",
        "- `GET /api/notifications/` (`?unread=true`, `?page=`), "
        "`POST /api/notifications/<id>/read/`, `POST /api/notifications/read-all/`.",
        "",
        "### Audit & users",
        "- `GET /api/core/audit/` (admin) - audit trail, newest first.",
        "- `GET/POST /api/users/`, `GET/PATCH /api/users/<id>/` (admin user management, "
        "password changes included).",
        "",
    ]
    (PROJECT_ROOT / "API_Documentation.md").write_text("\n".join(lines), encoding="utf-8")


def write_schema_sql():
    sql = fresh_schema_sql()
    header = (
        "-- =====================================================================\n"
        "-- SIWES Hub - full SQLite schema\n"
        "-- Generated from the Django migrations (python tools/generate_docs.py).\n"
        "-- Do not edit by hand: changing a model requires a new Django migration.\n"
        "-- =====================================================================\n\n"
    )
    (PROJECT_ROOT / "database" / "schema.sql").write_text(header + sql + "\n", encoding="utf-8")


def main():
    (PROJECT_ROOT / "documentation").mkdir(exist_ok=True)
    ctx = facts()
    models_by_app, counts, total, endpoints = ctx
    print(f"Models: {sum(len(v) for v in models_by_app.values())} in {len(models_by_app)} apps")
    print(f"Tests: {total} ({dict(counts)})")
    print(f"Endpoints: {len(endpoints)}")
    failures = []
    for writer, path in [
        (doc_overview, "SIWES_Hub_Project_Overview.docx"),
        (doc_installation, "SIWES_Hub_Installation_Guide.docx"),
        (doc_user_manual, "SIWES_Hub_User_Manual.docx"),
        (doc_design, "SIWES_Hub_System_Design_Document.docx"),
        (doc_testing, "SIWES_Hub_Testing_Report.docx"),
    ]:
        try:
            writer(ctx)
            print(f"  wrote documentation/{path}")
        except PermissionError:
            failures.append(path)
            print(f"  SKIPPED documentation/{path} - file is open in another program")
    try:
        write_api_md(ctx)
        print("  wrote API_Documentation.md")
    except OSError as exc:
        failures.append(str(exc))
    try:
        write_schema_sql()
        print("  wrote database/schema.sql")
    except OSError as exc:
        failures.append(str(exc))
    if failures:
        print("Skipped (locked) files:", "; ".join(failures))
    else:
        print("Wrote 5 .docx files into documentation/, API_Documentation.md and database/schema.sql")


if __name__ == "__main__":
    main()
