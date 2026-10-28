/* ==========================================================================
   SIWES Hub - supervisors.js
   Supervisors page (administrator only):
     register, edit and deactivate institution supervisors - the same way
     students are managed. Students see their own supervisor via the profile.
   ========================================================================== */

let supervisorsState = { page: 1 };

/** A supervisor whose self-registered account still waits for approval. */
function supervisorNeedsApproval(supervisor) {
  return Boolean(supervisor.is_pending) || Boolean(supervisor.user_is_active === false && supervisor.is_active);
}

/** Status badge that tells "pending approval" apart from plain "inactive". */
function supervisorStatusBadge(supervisor) {
  if (supervisorNeedsApproval(supervisor)) {
    return '<span class="badge badge-pending">pending approval</span>';
  }
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
        <thead><tr><th>Supervisor</th><th>Staff ID</th><th>Department</th><th>Email</th><th>Assigned students</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${response.results.map((supervisor) => `
            <tr>
              <td><strong>${escapeHtml(supervisor.full_name)}</strong>${supervisor.title ? `<br><span class="muted small">${escapeHtml(supervisor.title)}</span>` : ""}<br><span class="muted small">@${escapeHtml(supervisor.username)}</span></td>
              <td>${escapeHtml(supervisor.staff_id || "-")}</td>
              <td>${escapeHtml(supervisor.department || "-")}</td>
              <td class="muted small">${escapeHtml(supervisor.email || "-")}</td>
              <td>${supervisor.assigned_students}</td>
              <td>${supervisorStatusBadge(supervisor)}</td>
              <td class="flex flex-wrap">
                <button class="btn btn-outline btn-sm" data-edit="${supervisor.id}"><i data-lucide="pencil"></i>Edit</button>
                ${supervisorNeedsApproval(supervisor)
                  ? `<button class="btn btn-primary btn-sm" data-approve="${supervisor.id}"><i data-lucide="user-check"></i>Approve</button>
                     <button class="btn btn-ghost btn-sm" data-reject="${supervisor.id}"><i data-lucide="user-x"></i>Reject</button>`
                  : supervisor.is_active
                    ? `<button class="btn btn-ghost btn-sm" data-deactivate="${supervisor.id}"><i data-lucide="user-x"></i></button>`
                    : `<button class="btn btn-outline btn-sm" data-approve="${supervisor.id}"><i data-lucide="user-check"></i>Reactivate</button>`}
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
  refreshIcons();

  const byId = new Map(response.results.map((supervisor) => [supervisor.id, supervisor]));
  listRoot.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openSupervisorForm(byId.get(Number(btn.dataset.edit)))));
  // Approve / reactivate: activates the profile and its paired user account.
  listRoot.querySelectorAll("[data-approve]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const supervisor = byId.get(Number(btn.dataset.approve));
      const action = supervisorNeedsApproval(supervisor) ? "approve" : "reactivate";
      const message = action === "approve"
        ? `Approve the supervisor account of ${supervisor.full_name}? They will be able to sign in immediately.`
        : `Reactivate the supervisor account of ${supervisor.full_name}?`;
      if (await confirmDialog(message, { okLabel: "Confirm" })) {
        const response = await api.patch(`/supervisors/${supervisor.id}/`, { is_active: true }, { showErrors: false });
        if (response.ok) {
          toast(`Supervisor ${action === "approve" ? "approved" : "reactivated"}.`, "success");
          renderSupervisors();
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
        const message =
          `Reject the supervisor registration of ${supervisor.full_name} (${supervisor.email || "no email"})? ` +
          "The account stays disabled and the applicant is notified that it was not approved.";
        if (await confirmDialog(message, { danger: true, okLabel: "Reject" })) {
          const response = await api.patch(`/supervisors/${supervisor.id}/`, { is_active: false }, { showErrors: false });
          if (response.ok) {
            toast("Supervisor registration rejected.", "success");
            renderSupervisors();
          }
        }
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
    <p class="small">Review the details in the table below (Edit opens the full form), then use
    <em>Approve</em> to grant sign-in access or <em>Reject</em> to decline: ${names}</p>`;
  section.style.display = "";
  refreshIcons();
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
