/* ==========================================================================
   SIWES Hub - reports.js
   Weekly reportbook page. behaviour depends on the signed-in role:
     student    -> create/edit/delete drafts, submit, see supervisor feedback
     supervisor -> review queue: open, approve, reject with feedback
     admin      -> read-only oversight with filters
   Mirrors logs.js in structure on purpose (same workflow, different data).
   ========================================================================== */

let reportsState = { page: 1, user: null, role: null };

async function initReportsPage() {
  reportsState.user = await initAppShell({ page: "weekly-reports", title: "Weekly Reports" });
  if (!reportsState.user) return;
  reportsState.role = reportsState.user.role;
  document.getElementById("newReportBtn").style.display = reportsState.role === "student" ? "" : "none";
  document.getElementById("newReportBtn").addEventListener("click", () => openReportForm());

  document.getElementById("statusFilter").addEventListener("change", () => {
    reportsState.page = 1;
    renderReports();
  });

  // Deep links: dashboard quick action (?action=new) or notification (?id=&mode=review)
  const params = new URLSearchParams(window.location.search);
  if (reportsState.role === "student" && params.get("action") === "new") {
    openReportForm();
  }
  if (reportsState.role === "supervisor" && params.get("id")) {
    const detail = await api.get(`/reports/${params.get("id")}/`, { showErrors: false });
    if (detail.ok && detail.data.status === "submitted") {
      openReportReviewDialog(detail.data);
    }
  }

  renderReports();
}

async function renderReports() {
  const listRoot = document.getElementById("reportsList");
  listRoot.innerHTML = loadingBlock();

  const params = new URLSearchParams();
  params.set("page", reportsState.page);
  params.set("page_size", 10);
  const status = document.getElementById("statusFilter").value;
  if (status) params.set("status", status);

  const response = await api.getPaged(`/reports/?${params.toString()}`);
  renderPager(document.getElementById("reportsPager"), response, (newPage) => {
    reportsState.page = newPage;
    renderReports();
  });

  if (!response.results.length) {
    const emptyMessage =
      reportsState.role === "student"
        ? "No weekly reports yet. Click 'New weekly report' to summarise your week."
        : "No reports match this filter.";
    listRoot.innerHTML = emptyState(emptyMessage, "calendar-days");
    return;
  }

  listRoot.innerHTML = response.results.map(reportCardHtml).join("");
  refreshIcons();
  wireReportActions(response.results);
}

function reportCardHtml(report) {
  const role = reportsState.role;
  const editable = role === "student" && ["draft", "rejected"].includes(report.status);
  const canReview = role === "supervisor" && report.status === "submitted";
  return `
    <div class="card mb-2" data-report="${report.id}">
      <div class="flex" style="justify-content: space-between; align-items:flex-start;">
        <div>
          <strong>Week of ${formatDate(report.week_start)}</strong>
          ${report.week_end ? `<span class="muted small">to ${formatDate(report.week_end)}</span>` : ""}
          ${role !== "student" ? `<span class="muted small">· ${escapeHtml(report.student_name)}</span>` : ""}
          ${statusBadge(report.status)}
        </div>
        <div class="flex flex-wrap">
          <button class="btn btn-ghost btn-sm" data-view="${report.id}"><i data-lucide="eye"></i>View</button>
          ${editable ? `<button class="btn btn-outline btn-sm" data-edit="${report.id}"><i data-lucide="pencil"></i>Edit</button>` : ""}
          ${editable ? `<button class="btn btn-ghost btn-sm" data-delete="${report.id}"><i data-lucide="trash-2"></i>Delete</button>` : ""}
          ${editable ? `<button class="btn btn-primary btn-sm" data-submit="${report.id}"><i data-lucide="send"></i>${report.status === "rejected" ? "Resubmit" : "Submit"}</button>` : ""}
          ${canReview ? `<button class="btn btn-primary btn-sm" data-review="${report.id}"><i data-lucide="clipboard-check"></i>Review</button>` : ""}
        </div>
      </div>
      <p class="muted small mt-1 mb-0">${escapeHtml((report.summary_of_activities || "").length > 160 ? report.summary_of_activities.slice(0, 160) + "..." : (report.summary_of_activities || ""))}</p>
      ${report.status === "rejected" && report.supervisor_comment ? `
      <p class="small mt-1 mb-0" style="color:var(--danger)"><strong>Supervisor:</strong> ${escapeHtml(report.supervisor_comment)}</p>` : ""}
      ${report.status === "approved" && report.supervisor_comment ? `
      <p class="small mt-1 mb-0" style="color:var(--success)"><strong>Supervisor:</strong> ${escapeHtml(report.supervisor_comment)}</p>` : ""}
    </div>`;
}

function wireReportActions(reports) {
  const byId = new Map(reports.map((report) => [report.id, report]));
  const listRoot = document.getElementById("reportsList");

  listRoot.querySelectorAll("[data-view]").forEach((btn) =>
    btn.addEventListener("click", () => showReportDetail(byId.get(Number(btn.dataset.view)))));

  listRoot.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openReportForm(byId.get(Number(btn.dataset.edit)))));

  listRoot.querySelectorAll("[data-delete]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const report = byId.get(Number(btn.dataset.delete));
      if (await confirmDialog("Delete this report? This cannot be undone.", { danger: true, okLabel: "Delete report" })) {
        const response = await api.del(`/reports/${report.id}/`);
        if (response.ok) {
          toast("Report deleted.", "success");
          renderReports();
        }
      }
    }));

  listRoot.querySelectorAll("[data-submit]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const report = byId.get(Number(btn.dataset.submit));
      const response = await api.post(`/reports/${report.id}/submit/`);
      if (response.ok) {
        toast("Report submitted for supervisor review.", "success");
        renderReports();
      }
    }));

  listRoot.querySelectorAll("[data-review]").forEach((btn) =>
    btn.addEventListener("click", () => openReportReviewDialog(byId.get(Number(btn.dataset.review)))));
}

/** Create / edit modal. */
async function openReportForm(existing) {
  const isEdit = Boolean(existing);
  const weekStart = existing?.week_start || currentWeekStart();
  const modal = openModal(isEdit ? "Edit weekly report" : "New weekly report", `
    <form id="reportForm" class="form-grid">
      <div class="field">
        <label for="weekStart">Week starting *</label>
        <input type="date" id="weekStart" name="week_start" value="${weekStart}" required>
        <p class="hint">Monday of the week being reported (${isEdit ? "existing draft" : "defaults to this week"}).</p>
      </div>
      <div class="field">
        <label for="weekEnd">Week ending (optional)</label>
        <input type="date" id="weekEnd" name="week_end" value="${existing?.week_end || ""}">
        <p class="hint">Fills in automatically if left empty.</p>
      </div>
      <div class="field full">
        <label for="reportSummary">Summary of activities *</label>
        <textarea id="reportSummary" name="summary_of_activities" required>${escapeHtml(existing?.summary_of_activities || "")}</textarea>
        <p class="hint">What did you do during the week?</p>
      </div>
      <div class="field full">
        <label for="reportChallenges">Challenges faced</label>
        <textarea id="reportChallenges" name="challenges_faced">${escapeHtml(existing?.challenges_faced || "")}</textarea>
      </div>
      <div class="field full">
        <label for="reportLessons">Lessons learned</label>
        <textarea id="reportLessons" name="lessons_learned">${escapeHtml(existing?.lessons_learned || "")}</textarea>
      </div>
      <div class="field full">
        <label for="reportSkills">Skills acquired</label>
        <input type="text" id="reportSkills" name="skills_acquired" value="${escapeHtml(existing?.skills_acquired || "")}" placeholder="e.g. React components, SQL joins">
      </div>
      ${existing?.supervisor_comment ? `<div class="full form-note"><strong>Supervisor feedback:</strong> ${escapeHtml(existing.supervisor_comment)}</div>` : ""}
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="reportSave"><i data-lucide="save"></i>${isEdit ? "Save changes" : "Save draft"}</button>
    </div>`);
  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#reportSave").addEventListener("click", async () => {
    const form = modal.querySelector("#reportForm");
    const payload = {
      week_start: form.week_start.value,
      week_end: form.week_end.value || null,
      summary_of_activities: form.summary_of_activities.value.trim(),
      challenges_faced: form.challenges_faced.value.trim(),
      lessons_learned: form.lessons_learned.value.trim(),
      skills_acquired: form.skills_acquired.value.trim(),
    };

    if (!payload.week_start) return toast("Pick the week start date.", "error");
    if (!payload.summary_of_activities) return toast("Please summarise your activities.", "error");

    const response = isEdit
      ? await api.patch(`/reports/${existing.id}/`, payload, { showErrors: false })
      : await api.post("/reports/", payload, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      const detail = response.data?.detail;
      if (detail) toast(detail, "error");
      return;
    }
    closeModal();
    toast(isEdit ? "Report updated." : "Draft saved. Submit it when ready.", "success");
    reportsState.page = 1;
    renderReports();
  });
}

/** Monday of the current week (page-timezone). */
function currentWeekStart() {
  const now = new Date();
  const day = now.getDay(); // 0 = Sunday
  const monday = new Date(now);
  monday.setDate(now.getDate() - ((day + 6) % 7));
  return monday.toISOString().slice(0, 10);
}

/** Read-only detail modal. */
function showReportDetail(report) {
  if (!report) return;
  openModal(`Weekly report - week of ${formatDate(report.week_start)}`, `
    <table class="data-table">
      <tbody>
        <tr><th style="width:150px">Student</th><td>${escapeHtml(report.student_name)}</td></tr>
        <tr><th>Matric No</th><td>${escapeHtml(report.matric_number)}</td></tr>
        <tr><th>Period</th><td>${formatDate(report.week_start)} to ${formatDate(report.week_end)}</td></tr>
        <tr><th>Status</th><td>${statusBadge(report.status)}</td></tr>
        <tr><th>Summary</th><td>${escapeHtml(report.summary_of_activities)}</td></tr>
        <tr><th>Challenges</th><td>${escapeHtml(report.challenges_faced || "-")}</td></tr>
        <tr><th>Lessons</th><td>${escapeHtml(report.lessons_learned || "-")}</td></tr>
        <tr><th>Skills</th><td>${escapeHtml(report.skills_acquired || "-")}</td></tr>
        <tr><th>Submitted</th><td>${formatDateTime(report.submitted_at)}</td></tr>
        ${report.supervisor_comment ? `<tr><th>Supervisor</th><td>${escapeHtml(report.supervisor_name || "")}<br><em>${escapeHtml(report.supervisor_comment)}</em></td></tr>` : ""}
        ${report.reviewed_at ? `<tr><th>Reviewed</th><td>${formatDateTime(report.reviewed_at)}</td></tr>` : ""}
      </tbody>
    </table>`);
}

/** Supervisor approve / reject modal. */
function openReportReviewDialog(report) {
  if (!report) return;
  const modal = openModal(`Review weekly report - ${escapeHtml(report.student_name)}`, `
    <div class="form-note">
      <strong>Week:</strong> ${formatDate(report.week_start)} to ${formatDate(report.week_end)}
    </div>
    <p class="small"><strong>Summary:</strong> ${escapeHtml(report.summary_of_activities)}</p>
    <p class="small"><strong>Challenges:</strong> ${escapeHtml(report.challenges_faced || "-")}</p>
    <p class="small"><strong>Lessons:</strong> ${escapeHtml(report.lessons_learned || "-")} · <strong>Skills:</strong> ${escapeHtml(report.skills_acquired || "-")}</p>
    <div class="field">
      <label for="reportReviewComment">Comment (required when rejecting)</label>
      <textarea id="reportReviewComment" name="comment" placeholder="Write feedback for the student..."></textarea>
    </div>
    <div class="modal-actions">
      <span></span>
      <button class="btn btn-danger" id="reportReject"><i data-lucide="x"></i>Reject</button>
      <button class="btn btn-primary" id="reportApprove"><i data-lucide="check"></i>Approve</button>
    </div>`, { wide: true });
  modal.querySelector("#reportReviewComment").focus();

  const sendReview = async (decision) => {
    const comment = modal.querySelector("#reportReviewComment").value.trim();
    if (decision === "reject" && !comment) {
      return toast("A reason is required when rejecting.", "error");
    }
    const response = await api.post(`/reports/${report.id}/review/`, { decision, comment }, { showErrors: false });
    if (!response.ok) {
      toast(errorMessage(response.data), "error");
      return;
    }
    closeModal();
    toast(decision === "approve" ? "Report approved. The student has been notified." : "Report rejected. The student has been notified.", "success");
    renderReports();
  };
  modal.querySelector("#reportApprove").addEventListener("click", () => sendReview("approve"));
  modal.querySelector("#reportReject").addEventListener("click", () => sendReview("reject"));
}
