/* ==========================================================================
   SIWES Hub - organizations.js
   Host organizations page:
     everyone -> browse organizations (read-only)
     admin    -> add, edit, deactivate + manage SIWES sessions
   ========================================================================== */

let organizationsState = { page: 1 };

async function initOrganizationsPage() {
  const user = await initAppShell({ page: "organizations", title: "Organizations", roles: ["admin"] });
  if (!user) return;

  document.getElementById("newOrganizationBtn").addEventListener("click", () => openOrganizationForm());
  document.getElementById("newSessionBtn").addEventListener("click", () => openSessionForm());

  const search = document.getElementById("organizationsSearch");
  search.addEventListener("input", () => {
    clearTimeout(organizationsState._searchTimer);
    organizationsState._searchTimer = setTimeout(() => { organizationsState.page = 1; renderOrganizations(); }, 250);
  });

  renderOrganizations();
  renderSessions();
}

/* ------------------------------------------------------------------ */
/* Organizations                                                        */
/* ------------------------------------------------------------------ */
async function renderOrganizations() {
  const listRoot = document.getElementById("organizationsList");
  listRoot.innerHTML = loadingBlock();

  const params = new URLSearchParams();
  params.set("page", organizationsState.page);
  params.set("page_size", 12);
  const search = document.getElementById("organizationsSearch").value;
  if (search) params.set("search", search);
  const active = document.getElementById("organizationsActiveFilter")?.value;
  if (active) params.set("is_active", active);

  const response = await api.getPaged(`/organizations/?${params.toString()}`);
  renderPager(document.getElementById("organizationsPager"), response, (newPage) => {
    organizationsState.page = newPage;
    renderOrganizations();
  });

  if (!response.results.length) {
    listRoot.innerHTML = emptyState("No organizations match this filter.", "building-2");
    return;
  }

  listRoot.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Organization</th><th>Industry</th><th>Contact</th><th>Placed students</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${response.results.map((organization) => `
            <tr>
              <td><strong>${escapeHtml(organization.name)}</strong><br><span class="muted small">${escapeHtml(organization.address || "")}</span></td>
              <td>${escapeHtml(organization.industry || "-")}</td>
              <td class="muted small">${escapeHtml(organization.contact_person || "-")}${organization.contact_phone ? `<br>${escapeHtml(organization.contact_phone)}` : ""}${organization.contact_email ? `<br>${escapeHtml(organization.contact_email)}` : ""}</td>
              <td>${organization.placed_students}</td>
              <td>${statusBadge(organization.is_active ? "active" : "inactive")}</td>
              <td class="flex flex-wrap">
                <button class="btn btn-outline btn-sm" data-edit="${organization.id}"><i data-lucide="pencil"></i>Edit</button>
                ${organization.is_active ? `<button class="btn btn-ghost btn-sm" data-deactivate="${organization.id}"><i data-lucide="power-off"></i></button>` : ""}
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
  refreshIcons();

  const byId = new Map(response.results.map((organization) => [organization.id, organization]));
  listRoot.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openOrganizationForm(byId.get(Number(btn.dataset.edit)))));
  listRoot.querySelectorAll("[data-deactivate]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const organization = byId.get(Number(btn.dataset.deactivate));
      if (await confirmDialog(`Deactivate ${organization.name}? Past placements keep the organization on record.`, { danger: true, okLabel: "Deactivate" })) {
        const response = await api.del(`/organizations/${organization.id}/`);
        if (response.ok) {
          toast("Organization deactivated.", "success");
          renderOrganizations();
        }
      }
    }));
}

function openOrganizationForm(existing) {
  const isEdit = Boolean(existing);
  const modal = openModal(isEdit ? `Edit organization - ${escapeHtml(existing.name)}` : "Add organization", `
    <form id="organizationForm" class="form-grid">
      <div class="field full">
        <label for="orgName">Name *</label>
        <input type="text" id="orgName" name="name" value="${escapeHtml(existing?.name || "")}" required>
      </div>
      <div class="field full">
        <label for="orgAddress">Address</label>
        <input type="text" id="orgAddress" name="address" value="${escapeHtml(existing?.address || "")}">
      </div>
      <div class="field">
        <label for="orgIndustry">Industry</label>
        <input type="text" id="orgIndustry" name="industry" value="${escapeHtml(existing?.industry || "")}" placeholder="e.g. Software development">
      </div>
      <div class="field">
        <label for="orgContact">Contact person</label>
        <input type="text" id="orgContact" name="contact_person" value="${escapeHtml(existing?.contact_person || "")}">
      </div>
      <div class="field">
        <label for="orgPhone">Contact phone</label>
        <input type="tel" id="orgPhone" name="contact_phone" value="${escapeHtml(existing?.contact_phone || "")}">
      </div>
      <div class="field">
        <label for="orgEmail">Contact email</label>
        <input type="email" id="orgEmail" name="contact_email" value="${escapeHtml(existing?.contact_email || "")}">
      </div>
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="orgSave"><i data-lucide="save"></i>${isEdit ? "Save changes" : "Add organization"}</button>
    </div>`);

  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#orgSave").addEventListener("click", async () => {
    const form = modal.querySelector("#organizationForm");
    const payload = {
      name: form.name.value.trim(),
      address: form.address.value.trim(),
      industry: form.industry.value.trim(),
      contact_person: form.contact_person.value.trim(),
      contact_phone: form.contact_phone.value.trim(),
      contact_email: form.contact_email.value.trim(),
    };
    if (!payload.name) return toast("Organization name is required.", "error");

    const response = isEdit
      ? await api.patch(`/organizations/${existing.id}/`, payload, { showErrors: false })
      : await api.post("/organizations/", payload, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      if (response.data?.detail) toast(response.data.detail, "error");
      return;
    }
    closeModal();
    toast(isEdit ? "Organization updated." : "Organization added.", "success");
    organizationsState.page = 1;
    renderOrganizations();
  });
}

/* ------------------------------------------------------------------ */
/* SIWES sessions                                                       */
/* ------------------------------------------------------------------ */
async function renderSessions() {
  const listRoot = document.getElementById("sessionsList");
  listRoot.innerHTML = loadingBlock();
  const sessions = await apiGetList("/core/sessions/?page_size=50");

  if (!sessions.length) {
    listRoot.innerHTML = `<p class="muted small">No SIWES sessions defined yet. Create one before assigning placements.</p>`;
    return;
  }

  listRoot.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Session</th><th>Period</th><th>Placements</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${sessions.map((session) => `
            <tr>
              <td><strong>${escapeHtml(session.name)}</strong>${session.description ? `<br><span class="muted small">${escapeHtml(session.description)}</span>` : ""}</td>
              <td class="muted small">${formatDate(session.start_date)} to ${formatDate(session.end_date)}</td>
              <td>${session.placements_count}</td>
              <td>${session.is_active ? '<span class="badge badge-confirmed" style="background:var(--success-bg);color:var(--success);border:1px solid #c4ecd3">active</span>' : '<span class="badge badge-neutral">ended</span>'}</td>
              <td class="flex flex-wrap">
                <button class="btn btn-outline btn-sm" data-session-edit="${session.id}"><i data-lucide="pencil"></i>Edit</button>
                ${session.is_active ? `<button class="btn btn-ghost btn-sm" data-session-end="${session.id}"><i data-lucide="flag"></i>End</button>` : ""}
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
  refreshIcons();

  const byId = new Map(sessions.map((session) => [session.id, session]));
  listRoot.querySelectorAll("[data-session-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openSessionForm(byId.get(Number(btn.dataset.sessionEdit)))));
  listRoot.querySelectorAll("[data-session-end]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const session = byId.get(Number(btn.dataset.sessionEnd));
      if (await confirmDialog(`End session "${session.name}"? Its placements stay but it will no longer accept new ones.`, { danger: true, okLabel: "End session" })) {
        const response = await api.patch(`/core/sessions/${session.id}/`, { is_active: false });
        if (response.ok) {
          toast("Session ended.", "success");
          renderSessions();
        }
      }
    }));
}

function openSessionForm(existing) {
  const isEdit = Boolean(existing);
  const modal = openModal(isEdit ? `Edit session - ${escapeHtml(existing.name)}` : "New SIWES session", `
    <form id="sessionForm" class="form-grid">
      <div class="field full">
        <label for="sesName">Session name *</label>
        <input type="text" id="sesName" name="name" value="${escapeHtml(existing?.name || "")}" placeholder="e.g. 2025/2026 Rain Semester" required>
      </div>
      <div class="field">
        <label for="sesStart">Start date *</label>
        <input type="date" id="sesStart" name="start_date" value="${existing?.start_date || ""}" required>
      </div>
      <div class="field">
        <label for="sesEnd">End date *</label>
        <input type="date" id="sesEnd" name="end_date" value="${existing?.end_date || ""}" required>
      </div>
      <div class="field full">
        <label for="sesDescription">Description</label>
        <input type="text" id="sesDescription" name="description" value="${escapeHtml(existing?.description || "")}">
      </div>
      <div class="field full">
        <label style="display:flex; gap:0.5rem; align-items:center; font-weight:400">
          <input type="checkbox" id="sesActive" name="is_active" style="width:auto" ${existing ? (existing.is_active ? "checked" : "") : "checked"}>
          Active session (assignable to placements)
        </label>
      </div>
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="sesSave"><i data-lucide="save"></i>${isEdit ? "Save changes" : "Create session"}</button>
    </div>`);

  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#sesSave").addEventListener("click", async () => {
    const form = modal.querySelector("#sessionForm");
    const payload = {
      name: form.name.value.trim(),
      start_date: form.start_date.value,
      end_date: form.end_date.value,
      description: form.description.value.trim(),
      is_active: form.is_active.checked,
    };
    if (!payload.name) return toast("Session name is required.", "error");
    if (!payload.start_date || !payload.end_date) return toast("Start and end dates are required.", "error");

    const response = isEdit
      ? await api.patch(`/core/sessions/${existing.id}/`, payload, { showErrors: false })
      : await api.post("/core/sessions/", payload, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      return;
    }
    closeModal();
    toast(isEdit ? "Session updated." : "Session created.", "success");
    renderSessions();
  });
}
