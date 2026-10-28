/* ==========================================================================
   SIWES Hub - announcements.js
   Announcements page:
     admin               -> publish, edit, deactivate announcements
     student/supervisor  -> read announcements + mark them as read
   ========================================================================== */

let announcementsState = { page: 1, role: null, audience: "all" };

async function initAnnouncementsPage() {
  const user = await initAppShell({ page: "announcements", title: "Announcements" });
  if (!user) return;
  announcementsState.role = user.role;

  document.getElementById("newAnnouncementBtn").style.display = user.role === "admin" ? "" : "none";
  document.getElementById("newAnnouncementBtn").addEventListener("click", () => openAnnouncementForm());
  if (user.role === "admin") {
    document.getElementById("audienceFilter").style.display = "";
  }

  document.getElementById("audienceFilter")?.addEventListener("change", () => {
    announcementsState.page = 1;
    renderAnnouncements();
  });

  renderAnnouncements();
}

async function renderAnnouncements() {
  const listRoot = document.getElementById("announcementsList");
  listRoot.innerHTML = loadingBlock();

  const params = new URLSearchParams();
  params.set("page", announcementsState.page);
  params.set("page_size", 10);
  const audience = document.getElementById("audienceFilter")?.value;
  if (audience && announcementsState.role === "admin") params.set("audience", audience);

  const response = await api.getPaged(`/announcements/?${params.toString()}`);
  renderPager(document.getElementById("announcementsPager"), response, (newPage) => {
    announcementsState.page = newPage;
    renderAnnouncements();
  });

  if (!response.results.length) {
    listRoot.innerHTML = emptyState("No announcements yet.", "megaphone");
    return;
  }

  listRoot.innerHTML = response.results.map((announcement) => `
    <div class="card mb-2" data-announcement="${announcement.id}">
      <div class="flex" style="justify-content: space-between; align-items:flex-start;">
        <div>
          <strong>${escapeHtml(announcement.title)}</strong>
          ${audienceBadge(announcement.audience)}
          ${announcement.read_by_me && announcementsState.role !== "admin" ? '<span class="badge badge-approved">read</span>' : ""}
          ${!announcement.is_active ? '<span class="badge badge-inactive">inactive</span>' : ""}
        </div>
        <span class="muted small">${formatDateTime(announcement.created_at)} · ${escapeHtml(announcement.created_by_name || "office")}</span>
      </div>
      <p class="small mt-1 mb-0" style="white-space: pre-wrap">${escapeHtml(announcement.content)}</p>
      <div class="flex flex-wrap mt-2">
        ${announcementsState.role === "admin" ? `
          <button class="btn btn-outline btn-sm" data-edit="${announcement.id}"><i data-lucide="pencil"></i>Edit</button>
          <button class="btn btn-ghost btn-sm" data-delete="${announcement.id}"><i data-lucide="trash-2"></i>Delete</button>` : ""}
        ${announcementsState.role !== "admin" && !announcement.read_by_me ? `
          <button class="btn btn-primary btn-sm" data-read="${announcement.id}"><i data-lucide="check"></i>Mark as read</button>` : ""}
      </div>
    </div>`).join("");
  refreshIcons();

  const byId = new Map(response.results.map((announcement) => [announcement.id, announcement]));
  listRoot.querySelectorAll("[data-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openAnnouncementForm(byId.get(Number(btn.dataset.edit)))));
  listRoot.querySelectorAll("[data-read]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      await api.post(`/announcements/${btn.dataset.read}/read/`);
      toast("Marked as read.", "success");
      renderAnnouncements();
    }));
  listRoot.querySelectorAll("[data-delete]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const announcement = byId.get(Number(btn.dataset.delete));
      if (await confirmDialog(`Delete announcement "${announcement.title}"? This permanently removes it.`, { danger: true, okLabel: "Delete" })) {
        const response = await api.del(`/announcements/${announcement.id}/`);
        if (response.ok) {
          toast("Announcement deleted.", "success");
          renderAnnouncements();
        }
      }
    }));
}

function audienceBadge(audience) {
  const labels = { all: "everyone", students: "students", supervisors: "supervisors" };
  const tone = audience === "students" ? "blue" : audience === "supervisors" ? "orange" : "green";
  return `<span class="badge badge-neutral" style="background:var(--${tone === "blue" ? "info" : tone === "orange" ? "warning" : "success"}-bg); color:var(--${tone === "blue" ? "info" : tone === "orange" ? "warning" : "success"})">${escapeHtml(labels[audience] || audience)}</span>`;
}

function openAnnouncementForm(existing) {
  const isEdit = Boolean(existing);
  const modal = openModal(isEdit ? "Edit announcement" : "New announcement", `
    <form id="announcementForm" class="form-grid">
      <div class="field full">
        <label for="annTitle">Title *</label>
        <input type="text" id="annTitle" name="title" value="${escapeHtml(existing?.title || "")}" required>
      </div>
      <div class="field full">
        <label for="annContent">Content *</label>
        <textarea id="annContent" name="content" required>${escapeHtml(existing?.content || "")}</textarea>
        <p class="hint">Everyone targeted receives a notification in their bell.</p>
      </div>
      <div class="field">
        <label for="annAudience">Audience *</label>
        <select id="annAudience" name="audience" required>
          <option value="all" ${existing?.audience === "all" ? "selected" : ""}>Everyone</option>
          <option value="students" ${existing?.audience === "students" ? "selected" : ""}>Students only</option>
          <option value="supervisors" ${existing?.audience === "supervisors" ? "selected" : ""}>Supervisors only</option>
        </select>
      </div>
      <div class="field">
        <label style="display:flex; gap:0.5rem; align-items:center; font-weight:400">
          <input type="checkbox" id="annActive" name="is_active" style="width:auto" ${existing ? (existing.is_active ? "checked" : "") : "checked"}>
          Active (visible to the audience)
        </label>
      </div>
    </form>
    <div class="modal-actions" style="margin-top:1rem">
      <button class="btn btn-ghost" data-cancel>Cancel</button>
      <button class="btn btn-primary" id="annSave"><i data-lucide="megaphone"></i>${isEdit ? "Save changes" : "Publish"}</button>
    </div>`);

  modal.querySelector("[data-cancel]").addEventListener("click", closeModal);
  modal.querySelector("#annSave").addEventListener("click", async () => {
    const form = modal.querySelector("#announcementForm");
    const payload = {
      title: form.title.value.trim(),
      content: form.content.value.trim(),
      audience: form.audience.value,
      is_active: form.is_active.checked,
    };
    if (!payload.title) return toast("A title is required.", "error");
    if (!payload.content) return toast("Content is required.", "error");

    const response = isEdit
      ? await api.patch(`/announcements/${existing.id}/`, payload, { showErrors: false })
      : await api.post("/announcements/", payload, { showErrors: false });
    if (!response.ok) {
      applyFieldErrors(form, response.data);
      return;
    }
    closeModal();
    toast(isEdit ? "Announcement updated." : "Announcement published. Notifications sent.", "success");
    announcementsState.page = 1;
    renderAnnouncements();
  });
}
