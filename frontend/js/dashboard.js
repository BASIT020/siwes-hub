/* ==========================================================================
   SIWES Hub - dashboard.js
   Renders the three role dashboards from GET /api/core/dashboard/.
   Every number is live data from the database - nothing is hard-coded.
   ========================================================================== */

async function loadStudentDashboard() {
  const user = await initAppShell({ page: "student-dashboard", title: "Student Dashboard" });
  if (!user) return;

  const root = document.getElementById("dashRoot");
  root.innerHTML = loadingBlock();
  const response = await api.get("/core/dashboard/");
  if (!response.ok) {
    root.innerHTML = emptyState("Could not load the dashboard. Try refreshing.", "triangle-alert");
    return;
  }
  const data = response.data;
  const stats = data.stats || {};
  const placement = data.placement;
  const attendance = stats.attendance || {};

  document.getElementById("welcomeText").textContent =
    `Welcome back, ${(data.profile.full_name || "").split(" ")[0]}!`;

  root.innerHTML = `
    <div class="stat-grid mb-2">
      ${statCard("book-open-text", stats.total_logs, "Total Daily Logs", "purple")}
      ${statCard("clock", stats.pending_logs, "Pending Review", "blue")}
      ${statCard("check-circle", stats.approved_logs, "Approved Logs", "green")}
      ${statCard("chart-pie", `${attendance.attendance_rate ?? 0}%`, `Attendance (${attendance.total_days ?? 0} days)`, "orange")}
      ${statCard("sparkles", stats.skills_count, "Skills Learned", "purple")}
    </div>
    <div class="grid-3">
      <div class="card">
        <div class="card-title"><i data-lucide="building-2"></i>My Placement</div>
        ${placement
          ? `<p class="mt-0 mb-0"><strong>${escapeHtml(placement.organization_name)}</strong></p>
             <p class="muted small mt-1 mb-2">Supervisor: ${escapeHtml(placement.supervisor_name || "-")}<br>
             Session: ${escapeHtml(placement.session_name || "-")}</p>
             <p class="muted small mt-0 mb-0">${formatDate(placement.start_date)} to ${formatDate(placement.end_date)}</p>`
          : `<p class="muted small">You have not been placed yet. The SIWES coordinator will assign your organization and supervisor, watch this space.</p>`}
      </div>
      <div class="card">
        <div class="card-title"><i data-lucide="folder-git-2"></i>My Project</div>
        ${data.project
          ? `<p class="mt-0 mb-0"><strong>${escapeHtml(data.project.title)}</strong></p>
             <p class="mt-1 mb-1">${statusBadge(data.project.review_status)}</p>
             ${data.project.supervisor_comment ? `<p class="muted small">${escapeHtml(data.project.supervisor_comment)}</p>` : ""}`
          : `<p class="muted small">No project yet. Add one on the My Project page.</p>`}
        <a class="btn btn-outline btn-sm mt-2" href="/pages/projects.html">Manage project</a>
      </div>
      <div class="card">
        <div class="card-title"><i data-lucide="megaphone"></i>Announcements</div>
        ${(data.announcements || []).map((a) => `
          <div class="list-row">
            <div>
              <div class="small" style="font-weight:600; color:var(--navy-800)">${escapeHtml(a.title)}</div>
              <div class="muted small">${escapeHtml(a.content.length > 90 ? a.content.slice(0, 90) + "..." : a.content)}</div>
            </div>
          </div>`).join("") || `<p class="muted small">No announcements so far.</p>`}
        <a class="small" href="/pages/announcements.html">See all</a>
      </div>
    </div>
    <div class="grid-2 mt-2">
      <div class="card">
        <div class="card-title"><i data-lucide="message-square-quote"></i>Recent Supervisor Feedback</div>
        ${(data.recent_feedback || []).length
          ? data.recent_feedback.map((f) => `
              <div class="list-row">
                <div>
                  <div class="small"><strong>${escapeHtml(f.source)}</strong> - ${formatDate(f.date)}</div>
                  <div class="muted small">${escapeHtml(f.comment || "(no comment)")}</div>
                </div>
                <span class="when">${statusBadge(f.status)}</span>
              </div>`).join("")
          : `<p class="muted small">No feedback yet - submit your logs to get reviewed.</p>`}
      </div>
      <div class="card">
        <div class="card-title"><i data-lucide="zap"></i>Quick actions</div>
        <div class="flex flex-wrap mt-1">
          <a class="btn btn-primary" href="/pages/daily-logs.html?action=new"><i data-lucide="plus"></i>New daily log</a>
          <a class="btn btn-outline" href="/pages/weekly-reports.html?action=new"><i data-lucide="calendar-days"></i>Weekly report</a>
          <a class="btn btn-outline" href="/pages/projects.html"><i data-lucide="folder-git-2"></i>Project</a>
          <a class="btn btn-ghost" href="/pages/announcements.html"><i data-lucide="megaphone"></i>Announcements</a>
        </div>
      </div>
    </div>`;
  refreshIcons();
}

async function loadSupervisorDashboard() {
  const user = await initAppShell({ page: "supervisor-dashboard", title: "Supervisor Dashboard" });
  if (!user) return;
  const root = document.getElementById("dashRoot");
  root.innerHTML = loadingBlock();
  const response = await api.get("/core/dashboard/");
  if (!response.ok) {
    root.innerHTML = emptyState("Could not load the dashboard.", "triangle-alert");
    return;
  }
  const data = response.data;
  const stats = data.stats || {};

  root.innerHTML = `
    <div class="stat-grid mb-2">
      ${statCard("users-round", stats.assigned_students, "Assigned Students", "purple")}
      ${statCard("clock", stats.pending_logs, "Pending Daily Logs", "orange")}
      ${statCard("calendar-days", stats.pending_reports, "Pending Reports", "blue")}
      ${statCard("folder-git-2", stats.pending_projects, "Projects to review", "green")}
    </div>
    <div class="grid-2">
      <div class="card" style="grid-column: 1 / -1;">
        <div class="card-title"><i data-lucide="users-round"></i>My Assigned Students</div>
        ${(data.assigned_students || []).length ? `
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Student</th><th>Matric No</th><th>Organization</th><th>Pending logs</th><th>Approved</th><th>Attendance</th><th></th></tr>
            </thead>
            <tbody>
              ${(data.assigned_students || []).map((s) => `
                <tr>
                  <td><strong>${escapeHtml(s.full_name)}</strong>${s.needs_attention ? ' <span class="badge badge-pending">attention</span>' : ""}</td>
                  <td>${escapeHtml(s.matric_number)}</td>
                  <td>${escapeHtml(s.organization || "-")}</td>
                  <td>${s.pending_logs}</td>
                  <td>${s.approved_logs}</td>
                  <td>${s.attendance_rate}%</td>
                  <td><a class="btn btn-ghost btn-sm" href="/pages/students.html?student=${s.id}">View</a></td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>` : emptyState("You have no assigned students yet. The coordinator assigns students to you.", "users-round")}
      </div>
      <div class="card" style="grid-column: 1 / -1;">
        <div class="card-title"><i data-lucide="history"></i>My Recent Reviews</div>
        ${(data.recent_reviews || []).length ? data.recent_reviews.map((r) => `
          <div class="list-row">
            <div>
              <div class="small"><strong>${escapeHtml(r.kind)}</strong> - ${escapeHtml(r.student)}</div>
              <div class="muted small">${escapeHtml(r.comment || "")}</div>
            </div>
            <span class="when">${formatDateTime(r.reviewed_at)} ${statusBadge(r.status)}</span>
          </div>`).join("") : `<p class="muted small">No reviews completed yet.</p>`}
      </div>
    </div>`;
  refreshIcons();
}

async function loadAdminDashboard() {
  const user = await initAppShell({ page: "admin-dashboard", title: "Administrator Dashboard" });
  if (!user) return;
  const root = document.getElementById("dashRoot");
  root.innerHTML = loadingBlock();
  const response = await api.get("/core/dashboard/");
  if (!response.ok) {
    root.innerHTML = emptyState("Could not load the dashboard.", "triangle-alert");
    return;
  }
  const data = response.data;
  const stats = data.stats || {};

  const maxStudents = Math.max(1, ...(data.organization_distribution || []).map((row) => row.students));
  root.innerHTML = `
    <div class="stat-grid mb-2">
      ${statCard("graduation-cap", stats.total_students, "Total Students", "purple")}
      ${statCard("users-round", stats.total_supervisors, "Total Supervisors", "blue")}
      ${statCard("building-2", stats.total_organizations, "Organizations", "green")}
      ${statCard("briefcase", stats.active_placements, "Active Placements", "orange")}
      ${stats.pending_supervisors > 0
        ? statCard("user-cog", stats.pending_supervisors, "Supervisor Approvals Pending", "orange")
        : ""}
    </div>
    <div class="stat-grid mb-2">
      ${statCard("clock", stats.submitted_logs, "Logs Pending Review", "orange")}
      ${statCard("calendar-days", stats.pending_reports, "Reports Pending Review", "blue")}
      ${statCard("folder-git-2", stats.pending_projects, "Projects Awaiting Review", "purple")}
      ${statCard("calendar-check", stats.students_present_today, "Present Today", "green")}
    </div>
    <div class="grid-2">
      <div class="card">
        <div class="card-title"><i data-lucide="building-2"></i>Top Host Organizations</div>
        ${(data.organization_distribution || []).length ? data.organization_distribution.map((row) => `
          <div class="bar-row">
            <span class="small">${escapeHtml(row.organization)}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${Math.round((row.students / maxStudents) * 100)}%"></div></div>
            <span class="small center">${row.students}</span>
          </div>`).join("") : `<p class="muted small">No active placements to display.</p>`}
      </div>
      <div class="card">
        <div class="card-title"><i data-lucide="milestone"></i>Active SIWES Session</div>
        ${data.active_session
          ? `<p class="mt-0 mb-0"><strong>${escapeHtml(data.active_session.name)}</strong></p>
             <p class="muted small mt-1 mb-0">${formatDate(data.active_session.start_date)} to ${formatDate(data.active_session.end_date)}</p>`
          : `<p class="muted small">No active session configured.</p>`}
        <div class="flex flex-wrap mt-2">
          <a class="btn btn-outline btn-sm" href="/pages/organizations.html">Organizations</a>
          <a class="btn btn-outline btn-sm" href="/pages/students.html">Students</a>
          <a class="btn btn-outline btn-sm" href="/pages/supervisors.html">Supervisors</a>
        </div>
      </div>
      <div class="card" style="grid-column: 1 / -1;">
        <div class="card-title"><i data-lucide="scroll-text"></i>Recent System Activity (audit trail)</div>
        ${(data.recent_activity || []).length ? data.recent_activity.map((entry) => `
          <div class="list-row">
            <div>
              <div class="small"><strong>${escapeHtml(entry.action)}</strong> - ${escapeHtml(entry.detail || "")}</div>
            </div>
            <span class="when">${formatDateTime(entry.timestamp)} · ${escapeHtml(entry.actor_name || "system")}</span>
          </div>`).join("") : `<p class="muted small">No activity recorded yet.</p>`}
      </div>
    </div>`;
  refreshIcons();
}
