"""Generate database/MIGRATIONS.md: every migration file per app with its
operation summary, derived from the project itself (not hand-written)."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402
django.setup()

from django.db.migrations.loader import MigrationLoader  # noqa: E402

loader = MigrationLoader(None, ignore_no_migrations=True)
by_app = {}
for (app, name), mig in loader.graph.nodes.items():
    deps = [d[1] for d in mig.dependencies if d[0] == app]
    desc = ", ".join(op.describe() or op.__class__.__name__ for op in mig.operations) or "(initial)"
    by_app.setdefault(app, []).append((name, deps, desc))

ORDER = ["accounts", "core", "organizations", "students", "supervisors", "logs",
         "reports", "attendance", "projects", "announcements", "notifications"]

lines = [
    "# SIWES Hub - Migration Reference",
    "",
    "Every migration currently applied to `database/data/db.sqlite3`, grouped by",
    "application. Generated from the project (tools/generate_migrations_doc.py);",
    "regenerate after adding migrations.",
    "",
    "Apply commands:",
    "",
    "```",
    "cd backend",
    "python manage.py migrate          # apply everything pending",
    "python manage.py showmigrations   # inspect applied state",
    "```",
    "",
]
total = 0
for app in ORDER:
    if app not in by_app:
        continue
    migrations = {n: (d, s) for n, d, s in by_app[app]}
    # order by dependency chain
    ordered = []
    pending = list(migrations)
    placed = set()
    while pending:
        progressed = False
        for name in list(pending):
            deps, _ = migrations[name]
            if all(d in placed for d in deps):
                ordered.append(name)
                placed.add(name)
                pending.remove(name)
                progressed = True
        if not progressed:
            ordered.extend(pending)
            break
    lines += [f"## {app} ({len(ordered)} migration{'s' if len(ordered) != 1 else ''})", ""]
    for name in ordered:
        total += 1
        lines.append(f"* `{name}` - {migrations[name][1]}")
    lines.append("")

lines += ["", f"**{total} migrations in total.**"]
out = PROJECT_ROOT / "database" / "MIGRATIONS.md"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {out} ({total} migrations)")
