/* ==========================================================================
   SIWES Hub - logs.js
   Daily logbook page. behaviour depends on the signed-in role:
     student    -> create/edit/delete drafts, submit, see reviews
     supervisor -> review queue: open, approve, reject with feedback
     admin      -> read-only oversight with filters
   ========================================================================== */

let logsState = { page: 1, user: null, role: null };

async function initLogsPage() {
  logsState.user = await initAppShell({ page: "daily-logs", title: "Daily Logs" });
  if (!logsState.user) return;
  logsState.role = logsState.user.role;
  document.getElementById("newLogBtn").style.display = logsState.role === "student" ? "" : "none";
  document.getElementById("newLogBtn").addEventListener("click", () => openLogForm());
  document.getElementById("statusFilter").addEventListener("change", () => {
    logsState.page = 1;
    renderLogs();
  });

  // Deep links: dashboard quick action (?action=new) or notification (?id=&mode=review)
  const params = new URLSearchParams(window.location.search);
  if (logsState.role === "student" && params.get("action") === "new") {
    openLogForm();
  }
  if (logsState.role === "supervisor" && params.get("id")) {
    const detail = await api.get(`/logs/${params.get("id")}/`, { showErrors: false });
    if (detail.ok && detail.data.status === "submitted") {
      openReviewDialog(detail.data);
    }
  }
  renderLogs();
}

async function renderLogs() {
  const listRoot = document.getElementById("logsList");
  listRoot.innerHTML = loadingBlock();

  const params = new URLSearchParams();
  params.set("page", logsState.page);
  params.set("page_size", 12);
  const status = document.getElementById("statusFilter").value;
  if (status) params.set("status", status);
  params.set("page_size", String(12));
  if (logsState.role === "supervisor" && status !== "submitted") {
    // Supervisors get the review queue by default
    params.set("status", "submitted");
  }
  const response = await api.getPaged(`/logs/?${params.toString()}`);
  if (!response.results.length) {
    const emptyMessage =
      logsState.role === "student"
        ? "You have no logs yet. Click 'New daily log' to record today's activities."
        : "No logs match this filter.";
    listRoot.innerHTML = emptyState(emptyMessage, "book-open-text");
    renderPager(document.getElementById("logsPager"), response, () => {});
    return;
  }
  renderPager(document.getElementById("logsPager"), response, (newPage) => {
    logsState.page = newPage;
    renderLogs();
  });

  listRoot.innerHTML = response.results.map(logCardHtml).join("");
  refreshIcons();
  wireLogActions(response.results);
}

function logCardHtml(log) {
  const role = logsState.role;
  const editable = role === "student" && ["draft", "rejected"].includes(log.status);
  const canReview = role === "supervisor" && log.status === "submitted";
  return `
    <div class="card mb-2" data-log="${log.id}">
      <div class="flex" style="justify-content: space-between; align-items:flex-start;">
        <div>
          <strong>${formatDate(log.log_date)}</strong>
          ${role !== "student" ? `<span class="muted small">· ${escapeHtml(log.student_name)}</span>` : ""}
          ${statusBadge(log.status)}
        </div>
        <div class="flex">
          <button class="btn btn-ghost btn-sm" data-view="${log.id}"><i data-lucide="eye"></i>View</button>
          ${editable ? `<button class="btn btn-outline btn-sm" data-edit="${log.id}"><i data-lucide="pencil"></i>Edit</button>` : ""}
          ${editable ? `<button class="btn btn-ghost btn-sm" data-delete="${log.id}"><i data-lucide="trash-2"></i>Delete</button>` : ""}
          ${log.status === "draft" && role === "student" ? `<button class="btn btn-primary btn-sm" data-submit="${log.id}"><i data-lucide="send"></i>Submit</button>` : ""}
          ${log.status === "rejected" && role === "student" ? `<button class="btn btn-primary btn-sm" data-submit="${log.id}"><i data-lucide="send"></i>Resubmit</button>` : ""}
          ${canReview ? `<button class="btn btn-primary btn-sm" data-review="${log.id}"><i data-lucide="clipboard-check"></i>Review</button>` : ""}
        </div>
      </div>
      <p class="muted small mt-1 mb-0">${escapeHtml(log.activities.length > 160 ? log.activities.slice(0, 160) + "..." : log.activities)}</p>
      ${log.status === "rejected" && log.supervisor_comment ? `
      <p class="small mt-1 mb-0" style="color:var(--danger)"><strong>Supervisor:</strong> ${escapeHtml(log.supervisor_comment)}</p>` : ""}
      ${log.status === "approved" && log.supervisor_comment ? `
      <p class="small mt-1 mb-0" style="color:var(--success)"><strong>Supervisor:</strong> ${escapeHtml(log.supervisor_comment)}</p>` : ""}
    </div>`;
}

function wireLogActions(logs) {
  const byId = new Map(logs.map((log) => [log.id, log]));
  const listRoot = document.getElementById("logsList");

  listRoot.querySelectorAll("[data-view]").forEach((btn) =>
    btn.addEventListener("click", () => showLogDetail(byId.get(Number(btn.dataset.view)))));

  listRoot.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openLogForm(byId.get(Number(btn.dataset.edit)))));

  listRoot.querySelectorAll("[data-delete]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const log = byId.get(Number(btn.dataset.delete));
      if (await confirmDialog("Delete this draft log? This cannot be undone.", { danger: true, okLabel: "Delete log" })) {
        const response = await api.del(`/logs/${log.id}/`);
        if (response.ok) {
          toast("Log deleted.", "success");
          renderLogs();
        }
      }
    }));

  listRoot.querySelectorAll("[data-submit]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const log = byId.get(Number(btn.dataset.submit));
      const response = await api.post(`/logs/${log.id}/submit/`);
      if (response.ok) {
        toast("Log submitted for supervisor review.", "success");
        renderLogs();
      }
    }));

  listRoot.querySelectorAll("[data-review]").forEach((btn) =>
    btn.addEventListener("click", () => openReviewDialog(byId.get(Number(btn.dataset.review)))));
}

/** Create / edit modal. */
async function openLogForm(existing) {
  const isEdit = Boolean(existing);
  const defaultDate = existing?.log_date || new Date().toISOString().slice(0, 10);
  const modal = openModal(isEdit ? "Edit daily log" : "New daily log", `
    <form id="logForm" class="form-grid">
      <div class="field">
        <label for="logDate">Date</label>
        <input type="date" id="logDate" name="log_date" value="${defaultDate}" ${isEdit && existing.status === "draft" ? "" : ""}>
        <p class="hint">One log per date.</p>
      </div>
      <div class="field">
        <label for="logHours">Hours spent (optional)</label>
        <input type="number" step="0.5" min="0" max="24" id="logHours" name="hours_spent" value="${existing?.hours_spent ?? ""}">
      </div>
      <div class="field full">
        <label for="logActivities">Activities performed *</label>
        <textarea id="logActivities" name="activities" required>${escapeHtml(existing?.activities || "")}</textarea>
        <p class="hint">Describe the tasks you carried out that day.</p>
      </div>
      <div class="field full">
        <label for="logTools">Tools / technologies used</label>
        <input type="text" id="logTools" name="tools_used" value="${escapeHtml(existing?.tools_used || "")}" placeholder="e.g. VS Code, Django, Figma">
      </div>
      <div class="field full">
        <label for="logSkills">Skills learned</label>
        <input type="text" id="logSkills" name="skills_learned" value="${escapeHtml(existing?.skills_learned || "")}" placeholder="e.g. Git workflow, API design">
      </div>
      ${existing?.supervisor_comment ? `<div class="full form-note"><strong>Supervisor feedback:</strong> ${escapeHtml(existing.supervisor_comment)}</div>` : ""}
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="logSave"><i data-lucide="save"></i>${isEdit ? "Save changes" : "Save draft"}</button>
    </div>`);
  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#logSave").addEventListener("click", async () => {
    const form = modal.querySelector("#logForm");
    const payload = {
      log_date: form.log_date.value,
      activities: form.activities.value.trim(),
      tools_used: form.tools_used.value.trim(),
      skills_learned: form.skills_learned.value.trim(),
    };
    if (form.hours_spent.value) payload.hours_spent = Number(form.hours_spent.value);

    if (!payload.log_date) return toast("Pick a date.", "error");
    if (!payload.activities) return toast("Please describe your activities.", "error");

    const response = isEdit
      ? await api.patch(`/logs/${existing.id}/`, payload, { showErrors: false })
      : await api.post("/logs/", payload, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      return;
    }
    closeModal();
    toast(isEdit ? "Log updated." : "Draft saved. Submit it when ready.", "success");
    logsState.page = 1;
    renderLogs();
  });
}

/** Read-only detail modal. */
function showLogDetail(log) {
  if (!log) return;
  openModal(`Daily log - ${formatDate(log.log_date)}`, `
    <table class="data-table">
      <tbody>
        <tr><th style="width:130px">Student</th><td>${escapeHtml(log.student_name)}</td></tr>
        <tr><th>Matric No</th><td>${escapeHtml(log.matric_number)}</td></tr>
        <tr><th>Status</th><td>${statusBadge(log.status)}</td></tr>
        <tr><th>Activities</th><td>${escapeHtml(log.activities)}</td></tr>
        <tr><th>Tools used</th><td>${escapeHtml(log.tools_used || "-")}</td></tr>
        <tr><th>Skills</th><td>${escapeHtml(log.skills_learned || "-")}</td></tr>
        <tr><th>Hours</th><td>${escapeHtml(String(log.hours_spent ?? "-"))}</td></tr>
        <tr><th>Submitted</th><td>${formatDateTime(log.submitted_at)}</td></tr>
        ${log.supervisor_comment ? `<tr><th>Supervisor</th><td>${escapeHtml(log.supervisor_name || "")}<br><em>${escapeHtml(log.supervisor_comment)}</em></td></tr>` : ""}
        ${log.reviewed_at ? `<tr><th>Reviewed</th><td>${formatDateTime(log.reviewed_at)}</td></tr>` : ""}
      </tbody>
    </table>`);
}

/** Supervisor approve / reject modal. */
function openReviewDialog(log) {
  if (!log) return;
  const modal = openModal(`Review log - ${escapeHtml(log.student_name)}`, `
    <div class="form-note">
      <strong>Log date:</strong> ${formatDate(log.log_date)}
    </div>
    <p class="small"><strong>Activities:</strong> ${escapeHtml(log.activities)}</p>
    <p class="small"><strong>Tools:</strong> ${escapeHtml(log.tools_used || "-")} · <strong>Skills:</strong> ${escapeHtml(log.skills_learned || "-")}</p>
    <div class="field">
      <label for="reviewComment">Comment (required when rejecting)</label>
      <textarea id="reviewComment" name="comment" placeholder="Write feedback for the student..."></textarea>
    </div>
    <div class="modal-actions">
      <span></span>
      <button class="btn btn-danger" id="reviewReject"><i data-lucide="x"></i>Reject</button>
      <button class="btn btn-primary" id="reviewApprove"><i data-lucide="check"></i>Approve</button>
    </div>`, { wide: true });
  modal.querySelector("#reviewComment").focus();

  const sendReview = async (decision) => {
    const comment = modal.querySelector("#reviewComment").value.trim();
    if (decision === "reject" && !comment) {
      return toast("A reason is required when rejecting.", "error");
    }
    const response = await api.post(`/logs/${log.id}/review/`, { decision, comment }, { showErrors: false });
    if (!response.ok) {
      toast(errorMessage(response.data), "error");
      return;
    }
    closeModal();
    toast(decision === "approve" ? "Log approved. The student has been notified." : "Log rejected. The student has been notified.", "success");
    renderLogs();
  };
  modal.querySelector("#reviewApprove").addEventListener("click", () => sendReview("approve"));
  modal.querySelector("#reviewReject").addEventListener("click", () => sendReview("reject"));
}
