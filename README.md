# SIWES Hub - SIWES Management & Monitoring Portal

A complete, local, database-backed web application for the **Students
Industrial Work Experience Scheme (SIWES)**: students keep digital daily
logbooks and weekly reports, supervisors review them and record attendance,
and the SIWES office manages users, placements, sessions and announcements —
all enforced server-side, with a full audit trail.

Built as an academic final-year project. Runs entirely on one Windows PC, no
internet connection required.

---

## Quick start

| Task | How |
|---|---|
| **Run the app** | Double-click `deployment\START_APP.bat` → browser opens `http://127.0.0.1:8000` |
| **Stop the app** | Double-click `deployment\STOP_APP.bat` |
| **First administrator** | The launcher asks for it once (hidden password prompt) — or run `manage.py bootstrap_admin` |
| **Registration site** | `http://127.0.0.1:8000/pages/register.html` (linked from the sign-in page) |
| **Build the portable package** | Double-click `deployment\BUILD_PORTABLE.bat` → `dist\SIWES-Hub-Portable.zip` |
| **Run elsewhere** | Copy `dist\SIWES-Hub-Portable` to any Windows PC, run its `deployment\START_APP.bat` |

The first start applies migrations, creates the SQLite database and asks (once,
with a hidden password prompt) for the first administrator account. Starting
the app again never duplicates data, never resets passwords and never creates
sample users.

## Accounts

| Account type | How it exists |
|---|---|
| Administrator (SIWES office) | Created once by `bootstrap_admin` (interactive, hidden password) — there is **no public registration** for administrators |
| Student | Self-service: **Create account → Student** on the registration page; active immediately |
| Supervisor | Self-service: **Create account → Supervisor**; stays **pending** until an administrator approves it on the Supervisors page |

`backend/core/management/commands/seed_demo.py` can build a labelled
demonstration dataset for lectures/exams, but it is **never** run by the
launcher and never touches existing account passwords unless explicitly asked
(`--refresh-passwords`).

## What's inside

```
backend/       Django 5.1 + Django REST Framework
  config/      settings, URL routing, page whitelist, WSGI
  accounts/    custom User model, session auth, login throttling
  core/        dashboard statistics, placements, SIWES sessions, audit trail
  logs/        daily logs + draft→submitted→approved/rejected workflow
  reports/     weekly reports + review workflow
  attendance/  attendance records, summaries, attendance rate
  projects/    one training project per student + supervisor review
  students/    student profiles + skills catalogue
  supervisors/ supervisor profiles + directory
  organizations/ placement companies
  announcements/ organisation-wide announcements (per-user read state)
  notifications/ per-user notification inbox
frontend/      vanilla HTML/CSS/JS pages served by Django itself (incl. registration)
database/      writable data dir (SQLite), schema.sql, migration reference
deployment/    START_APP.bat, STOP_APP.bat, BUILD_PORTABLE.bat, embedded runtime cache
tests/         tests/api_smoke.py - 30-check live workflow smoke test
documentation/ project .docx set (overview, install, user manual, design, testing)
tools/         generators used to produce the documentation
```

## Testing

```bat
cd backend
..\.venv\Scripts\python.exe manage.py test accounts core students logs reports attendance projects announcements
:: → 74 tests, all passing

:: with the server running:
..\.venv\Scripts\python.exe ..\tests\api_smoke.py
:: → 30 checks, 0 failures
```

## Documentation

* `documentation\SIWES_Hub_Project_Overview.docx`
* `documentation\SIWES_Hub_Installation_Guide.docx`
* `documentation\SIWES_Hub_User_Manual.docx`
* `documentation\SIWES_Hub_System_Design_Document.docx`
* `documentation\SIWES_Hub_Testing_Report.docx`
* `API_Documentation.md` (root) — every endpoint with method, access and payload
* `database\README.md`, `database\schema.sql`, `database\MIGRATIONS.md`

## Notes & limitations

* Single-computer demonstration system: `DEBUG=True`, bound to `127.0.0.1`, SQLite file database.
* Not hardened for production/internet use (no TLS, no e-mail verification).
* All data lives in `database\data\db.sqlite3` — copy that file to back up.
