/* ==========================================================================
   SIWES Hub - supervisors.js
   Supervisors page (administrator only):
     register, edit and deactivate institution supervisors - the same way
     students are managed. Students see their own supervisor via the profile.
   ========================================================================== */

let supervisorsState = { page: 1, status: "" };

/** A supervisor whose self-registered account still waits for approval. */
function supervisorNeedsApproval(supervisor) {
  return Boolean(supervisor.is_pending) || Boolean(supervisor.user_is_active === false && supervisor.is_active);
}

/** Status badge from the server-computed application status (falls back to
 * the legacy is_pending/is_active flags for older cached responses). */
function supervisorStatusBadge(supervisor) {
  if (supervisor.status === "pending" || supervisorNeedsApproval(supervisor)) {
    return '<span class="badge badge-pending">pending approval</span>';
  }
  if (supervisor.status === "rejected") return statusBadge("rejected");
  return statusBadge(supervisor.is_active ? "active" : "inactive");
}

async function initSupervisorsPage() {
  const user = await initAppShell({ page: "supervisors", title: "Supervisors", roles: ["admin"] });
  if (!user) return;

  document.getElementById("newSupervisorBtn").addEventListener("click", () => openSupervisorForm());

  const search = document.getElementById("supervisorsSearch");
  search.addEventListener("input", () => {
    clearTimeout(supervisorsState._searchTimer);
    supervisorsState._searchTimer = setTimeout(() => { supervisorsState.page = 1; renderSupervisors(); }, 250);
  });
  const statusFilter = document.getElementById("supervisorsStatus");
  if (statusFilter) {
    statusFilter.addEventListener("change", () => {
      supervisorsState.status = statusFilter.value;
      supervisorsState.page = 1;
      renderSupervisors();
    });
  }

  renderSupervisors();
}

async function renderSupervisors() {
  const listRoot = document.getElementById("supervisorsList");
  listRoot.innerHTML = loadingBlock();

  const params = new URLSearchParams();
  params.set("page", supervisorsState.page);
  params.set("page_size", 12);
  const search = document.getElementById("supervisorsSearch").value;
  if (search) params.set("search", search);
  if (supervisorsState.status) params.set("status", supervisorsState.status);

  const response = await api.getPaged(`/supervisors/?${params.toString()}`);
  renderPager(document.getElementById("supervisorsPager"), response, (newPage) => {
    supervisorsState.page = newPage;
    renderSupervisors();
  });

  if (!response.results.length) {
    listRoot.innerHTML = emptyState("No supervisors match this filter.", "users-round");
    return;
  }

  listRoot.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Supervisor</th><th>Staff ID</th><th>Department</th><th>Email</th><th>Assigned students</th><th>Registered</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${response.results.map((supervisor) => `
            <tr>
              <td><strong>${escapeHtml(supervisor.full_name)}</strong>${supervisor.title ? `<br><span class="muted small">${escapeHtml(supervisor.title)}</span>` : ""}<br><span class="muted small">@${escapeHtml(supervisor.username)}</span></td>
              <td>${escapeHtml(supervisor.staff_id || "-")}</td>
              <td>${escapeHtml(supervisor.department || "-")}</td>
              <td class="muted small">${escapeHtml(supervisor.email || "-")}</td>
              <td>${supervisor.assigned_students}</td>
              <td class="muted small">${formatDate(supervisor.created_at)}</td>
              <td>${supervisorStatusBadge(supervisor)}</td>
              <td class="flex flex-wrap">
                <button class="btn btn-outline btn-sm" data-view="${supervisor.id}"><i data-lucide="eye"></i>Details</button>
                <button class="btn btn-outline btn-sm" data-edit="${supervisor.id}"><i data-lucide="pencil"></i>Edit</button>
                ${supervisor.status === "pending" || supervisorNeedsApproval(supervisor)
                  ? `<button class="btn btn-primary btn-sm" data-approve="${supervisor.id}"><i data-lucide="user-check"></i>Approve</button>
                     <button class="btn btn-ghost btn-sm" data-reject="${supervisor.id}"><i data-lucide="user-x"></i>Reject</button>`
                  : supervisor.is_active
                    ? `<button class="btn btn-ghost btn-sm" data-deactivate="${supervisor.id}"><i data-lucide="user-x"></i></button>`
                    : `<button class="btn btn-outline btn-sm" data-approve="${supervisor.id}"><i data-lucide="user-check"></i>${supervisor.status === "rejected" ? "Reactivate" : "Approve"}</button>`}
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
  refreshIcons();

  const byId = new Map(response.results.map((supervisor) => [supervisor.id, supervisor]));
  listRoot.querySelectorAll("[data-view]").forEach((btn) =>
    btn.addEventListener("click", () => openSupervisorDetails(byId.get(Number(btn.dataset.view)))));
  listRoot.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openSupervisorForm(byId.get(Number(btn.dataset.edit)))));
  // Approve / reactivate: activates the profile and its paired user account,
  // stamps the approving administrator and the decision time server-side.
  listRoot.querySelectorAll("[data-approve]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const supervisor = byId.get(Number(btn.dataset.approve));
      const action = supervisor.status === "pending" || supervisorNeedsApproval(supervisor) ? "approve" : "reactivate";
      const message = action === "approve"
        ? `Confirm approval for ${supervisor.full_name}?\n\n`
          + (supervisor.email ? `Email: ${supervisor.email}\n` : "")
          + (supervisor.staff_id ? `Staff ID: ${supervisor.staff_id}\n` : "")
          + (supervisor.department ? `Department: ${supervisor.department}\n` : "")
          + (supervisor.title ? `Job title: ${supervisor.title}\n` : "")
          + `\nThey will be able to sign in immediately.`
        : `Reactivate the supervisor account of ${supervisor.full_name}?`;
      if (await confirmDialog(message, { okLabel: "Approve" })) {
        const response = await api.post(`/supervisors/${supervisor.id}/approve/`, {}, { showErrors: false });
        if (response.ok) {
          toast(`Supervisor ${action === "approve" ? "approved" : "reactivated"}.`, "success");
          renderSupervisors();
          renderPendingBanner();
        } else {
          toast(response.data?.detail || "Approval failed.", "error");
        }
      }
    }));
  listRoot.querySelectorAll("[data-reject]").forEach((btn) =>
    {
      // Rejecting a pending registration is NOT the same as deactivating a
      // working supervisor: it leaves no working account behind and the
      // applicant is told their registration was not approved.
      btn.addEventListener("click", async () => {
        const supervisor = byId.get(Number(btn.dataset.reject));
        openRejectSupervisorModal(supervisor);
      });
    });
  listRoot.querySelectorAll("[data-deactivate]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const supervisor = byId.get(Number(btn.dataset.deactivate));
      if (await confirmDialog(`Deactivate supervisor ${supervisor.full_name}? Assigned students will only be reassigned to keep working properly.`, { danger: true, okLabel: "Deactivate" })) {
        const response = await api.patch(`/supervisors/${supervisor.id}/`, { is_active: false }, { showErrors: false });
        if (response.ok) {
          toast("Supervisor deactivated.", "success");
          renderSupervisors();
        }
      }
    }));

  renderPendingBanner();
}

/** "Pending supervisor approvals" summary above the supervisor table. */
async function renderPendingBanner() {
  const section = document.getElementById("pendingApprovals");
  if (!section) return;
  const response = await api.getPaged("/supervisors/?pending=true&page_size=5");
  if (!response.results.length) {
    section.style.display = "none";
    return;
  }
  const names = response.results.map((s) => escapeHtml(s.full_name || s.username)).join(", ");
  section.querySelector("#pendingApprovalsBody").innerHTML = `
    <strong>${response.count} supervisor registration${response.count === 1 ? "" : "s"} awaiting approval</strong>
    <p class="small">Review the details in the table below (Details/Edit opens the full record), then use
    <em>Approve</em> to grant sign-in access or <em>Reject</em> to decline: ${names}</p>`;
  section.style.display = "";
  refreshIcons();
}

/** Administrator decline dialog: a written reason is required and stored. */
function openRejectSupervisorModal(supervisor) {
  const modal = openModal(`Reject registration - ${escapeHtml(supervisor.full_name)}`, `
    <p class="small" style="margin-top:0">Reject the supervisor registration of
    <strong>${escapeHtml(supervisor.full_name)}</strong> (${escapeHtml(supervisor.email || "no email")})?
    The account stays disabled, the applicant is notified, and your reason is recorded.</p>
    <form id="rejectForm" class="form-grid">
      <div class="field full">
        <label for="rejectReason">Rejection reason *</label>
        <textarea id="rejectReason" name="reason" rows="3" required
          placeholder="e.g. Staff ID could not be verified with the department"></textarea>
      </div>
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-danger" id="rejectSave" style="background:var(--danger,#b3261e);color:#fff;border:none">
        <i data-lucide="user-x"></i>Reject registration
      </button>
    </div>`);

  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#rejectSave").addEventListener("click", async () => {
    const reason = modal.querySelector("#rejectReason").value.trim();
    if (!reason) return toast("A rejection reason is required.", "error");
    const response = await api.post(`/supervisors/${supervisor.id}/reject/`, { reason }, { showErrors: false });
    if (response.ok) {
      closeModal();
      toast("Supervisor registration rejected.", "success");
      renderSupervisors();
      renderPendingBanner();
    } else {
      toast(response.data?.reason || response.data?.detail || "Rejection failed.", "error");
    }
  });
  refreshIcons();
}

/** Administrator read-only details of a supervisor record / application. */
function openSupervisorDetails(supervisor) {
  const statusRow = () => {
    if (supervisor.status === "pending") return '<span class="badge badge-pending">pending approval</span>';
    return supervisorStatusBadge(supervisor);
  };
  const modal = openModal(`Supervisor details - ${escapeHtml(supervisor.full_name)}`, `
    <div class="form-grid" style="margin-top:.25rem">
      <div class="field"><span class="muted small">Full name</span><br><strong>${escapeHtml(supervisor.full_name)}</strong></div>
      <div class="field"><span class="muted small">Username</span><br><span>${escapeHtml(supervisor.username)}</span></div>
      <div class="field"><span class="muted small">Email</span><br><span>${escapeHtml(supervisor.email || "-")}</span></div>
      <div class="field"><span class="muted small">Staff ID</span><br><span>${escapeHtml(supervisor.staff_id || "-")}</span></div>
      <div class="field"><span class="muted small">Job title</span><br><span>${escapeHtml(supervisor.title || "-")}</span></div>
      <div class="field"><span class="muted small">Department</span><br><span>${escapeHtml(supervisor.department || "-")}</span></div>
      <div class="field"><span class="muted small">Registration date</span><br><span>${formatDateTime(supervisor.created_at)}</span></div>
      <div class="field"><span class="muted small">Account status</span><br>${statusRow()}</div>
      <div class="field"><span class="muted small">Assigned students</span><br><span>${supervisor.assigned_students}</span></div>
      <div class="field"><span class="muted small">Approved on</span><br><span>${supervisor.approved_at ? formatDateTime(supervisor.approved_at) + (supervisor.approved_by_name ? " by " + escapeHtml(supervisor.approved_by_name) : "") : "-"}</span></div>
      ${supervisor.status === "rejected" && supervisor.rejected_reason ? `
      <div class="field full"><span class="muted small">Rejected on</span><br>
        <span>${formatDateTime(supervisor.rejected_at)}${supervisor.rejected_by_name ? " by " + escapeHtml(supervisor.rejected_by_name) : ""}</span>
        <p class="hint" style="margin:.35rem 0 0">Reason: ${escapeHtml(supervisor.rejected_reason)}</p>
      </div>` : ""}
    </div>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-primary" data-cancel>Close</button>
    </div>`);
  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
}

function openSupervisorForm(existing) {
  const isEdit = Boolean(existing);
  const modal = openModal(isEdit ? `Edit supervisor - ${escapeHtml(existing.full_name)}` : "Register supervisor", `
    <form id="supervisorForm" class="form-grid">
      ${isEdit ? "" : `
      <div class="field">
        <label for="supUsername">Username *</label>
        <input type="text" id="supUsername" name="username" required>
      </div>
      <div class="field">
        <label for="supPassword">Temporary password *</label>
        <input type="text" id="supPassword" name="password" required>
        <p class="hint">At least 6 characters.</p>
      </div>`}
      <div class="field">
        <label for="supFullName">Full name *</label>
        <input type="text" id="supFullName" name="full_name" value="${escapeHtml(existing?.full_name || "")}" required>
      </div>
      <div class="field">
        <label for="supTitle">Title</label>
        <input type="text" id="supTitle" name="title" value="${escapeHtml(existing?.title || "")}" placeholder="e.g. Mr., Dr., Engr.">
      </div>
      <div class="field">
        <label for="supStaffId">Staff ID</label>
        <input type="text" id="supStaffId" name="staff_id" value="${escapeHtml(existing?.staff_id || "")}">
      </div>
      <div class="field">
        <label for="supEmail">Email</label>
        <input type="email" id="supEmail" name="email" value="${escapeHtml(existing?.email || "")}">
      </div>
      <div class="field">
        <label for="supDepartment">Department</label>
        <input type="text" id="supDepartment" name="department" value="${escapeHtml(existing?.department || "")}">
      </div>
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="supSave"><i data-lucide="save"></i>${isEdit ? "Save changes" : "Register supervisor"}</button>
    </div>`);

  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#supSave").addEventListener("click", async () => {
    const form = modal.querySelector("#supervisorForm");
    const base = {
      full_name: form.full_name.value.trim(),
      email: form.email.value.trim(),
      title: form.title.value.trim(),
      staff_id: form.staff_id.value.trim(),
      department: form.department.value.trim(),
    };
    if (!base.full_name) return toast("Full name is required.", "error");

    const payload = isEdit ? base : {
      ...base,
      username: form.username.value.trim(),
      password: form.password.value,
    };
    if (!isEdit && !payload.username) return toast("Username is required.", "error");

    const response = isEdit
      ? await api.patch(`/supervisors/${existing.id}/`, payload, { showErrors: false })
      : await api.post("/supervisors/", payload, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      if (response.data?.detail) toast(response.data.detail, "error");
      return;
    }
    closeModal();
    toast(isEdit ? "Supervisor updated." : "Supervisor registered. Assign students to them on the Students page.", "success");
    supervisorsState.page = 1;
    renderSupervisors();
  });
}
