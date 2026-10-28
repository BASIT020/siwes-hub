/* ==========================================================================
   SIWES Hub - projects.js
   Student project page:
     student    -> create/edit own project, submit for review, see feedback
     supervisor -> review queue for assigned students' projects
     admin      -> read-only overview of all projects
   ========================================================================== */

let projectsState = { page: 1, user: null, role: null };

async function initProjectsPage() {
  projectsState.user = await initAppShell({ page: "projects", title: "SIWES Project" });
  if (!projectsState.user) return;
  projectsState.role = projectsState.user.role;

  if (projectsState.role === "student") {
    document.getElementById("studentProjectRoot").style.display = "";
    document.getElementById("projectsListWrap").style.display = "none";
    await loadMyProject();

    // Notification deep link: ?mode=review rejected focus is not needed here.
  } else {
    document.getElementById("studentProjectRoot").style.display = "none";
    document.getElementById("projectsListWrap").style.display = "";
    document.getElementById("reviewStatusFilter").addEventListener("change", () => {
      projectsState.page = 1;
      renderProjects();
    });
    await renderProjects();

    // Deep link from a notification: open the review dialog directly.
    const params = new URLSearchParams(window.location.search);
    if (projectsState.role === "supervisor" && params.get("id")) {
      const target = await findProjectById(Number(params.get("id")));
      if (target && target.review_status === "submitted") openProjectReviewDialog(target);
    }
  }
}

/** Student: load and render their own project card. */
async function loadMyProject() {
  const root = document.getElementById("studentProjectRoot");
  root.innerHTML = loadingBlock();
  const response = await api.get("/projects/me/", { showErrors: false });
  if (!response.ok) {
    root.innerHTML = emptyState("Could not load your project. Try refreshing.", "triangle-alert");
    return;
  }
  const project = response.data && response.data.project === null ? null : response.data;
  renderMyProject(project);
}

function renderMyProject(project) {
  const root = document.getElementById("studentProjectRoot");
  if (!project) {
    root.innerHTML = `
      <div class="card">
        <div class="card-title"><i data-lucide="folder-plus"></i>Create your SIWES project</div>
        <p class="muted small">Describe the project you are building during your industrial training. Save it when you are ready, then submit it to your supervisor for approval.</p>
        ${projectFormHtml(null)}
        <div class="flex mt-2">
          <button class="btn btn-primary" id="projectSaveBtn"><i data-lucide="save"></i>Save project</button>
        </div>
      </div>`;
  } else {
    const editable = project.review_status === "not_submitted" || project.review_status === "rejected";
    root.innerHTML = `
      <div class="card mb-2">
        <div class="flex" style="justify-content: space-between; align-items:flex-start;">
          <div>
            <div class="card-title" style="margin-bottom:0.2rem"><i data-lucide="folder-git-2"></i>${escapeHtml(project.title)}</div>
            ${statusBadge(project.review_status)}
          </div>
        </div>
        <dl class="mt-2">
          <p class="small mb-2"><strong>Description:</strong> ${escapeHtml(project.description || "-")}</p>
          <p class="small mb-2"><strong>Objectives:</strong> ${escapeHtml(project.objectives || "-")}</p>
          <p class="small mb-2"><strong>Technologies:</strong> ${escapeHtml(project.technologies || "-")}</p>
          ${project.submitted_at ? `<p class="small mb-2 muted">Submitted: ${formatDateTime(project.submitted_at)}</p>` : ""}
          ${project.reviewed_at ? `<p class="small mb-2 muted">Reviewed: ${formatDateTime(project.reviewed_at)} by ${escapeHtml(project.supervisor_name || "-")}</p>` : ""}
          ${project.supervisor_comment ? `
            <div class="form-note"><strong>Supervisor feedback:</strong> ${escapeHtml(project.supervisor_comment)}</div>` : ""}
        </dl>
        ${editable ? `
          <details class="mt-2">
            <summary class="btn btn-outline btn-sm" style="cursor:pointer"><i data-lucide="pencil"></i>Edit project</summary>
            <div class="mt-2">${projectFormHtml(project)}
              <div class="flex mt-2">
                <button class="btn btn-primary" id="projectSaveBtn"><i data-lucide="save"></i>Save changes</button>
              </div>
            </div>
          </details>` : `
          <p class="muted small mt-2">This project is ${escapeHtml(project.review_status.replace("_", " "))} and can no longer be edited${project.review_status === "submitted" ? " - your supervisor will review it" : ""}.</p>`}
      </div>
      ${(editable) ? `
      <div class="card">
        <div class="card-title"><i data-lucide="send"></i>Submit for review</div>
        <p class="muted small mb-2">Send your project to your assigned supervisor. They will approve it or send it back with feedback.</p>
        <button class="btn btn-primary" id="projectSubmitBtn"><i data-lucide="send"></i>${project.review_status === "rejected" ? "Resubmit for review" : "Submit for review"}</button>
      </div>` : ""}`;
  }
  refreshIcons();

  root.querySelector("#projectSaveBtn")?.addEventListener("click", saveProject);
  root.querySelector("#projectSubmitBtn")?.addEventListener("click", async () => {
    const response = await api.post("/projects/me/submit/");
    if (response.ok) {
      toast("Project submitted for review.", "success");
      loadMyProject();
    }
  });
}

/** Shared create + edit form fields. */
function projectFormHtml(project) {
  return `
    <form id="projectForm" class="form-grid">
      <div class="field full">
        <label for="projTitle">Project title *</label>
        <input type="text" id="projTitle" name="title" value="${escapeHtml(project?.title || "")}" required>
      </div>
      <div class="field full">
        <label for="projDescription">Description</label>
        <textarea id="projDescription" name="description">${escapeHtml(project?.description || "")}</textarea>
        <p class="hint">What does the project do?</p>
      </div>
      <div class="field full">
        <label for="projObjectives">Objectives</label>
        <textarea id="projObjectives" name="objectives">${escapeHtml(project?.objectives || "")}</textarea>
      </div>
      <div class="field full">
        <label for="projTech">Technologies / tools</label>
        <input type="text" id="projTech" name="technologies" value="${escapeHtml(project?.technologies || "")}" placeholder="e.g. HTML, CSS, JavaScript, Django">
      </div>
    </form>`;
}

async function saveProject() {
  const form = document.getElementById("projectForm");
  if (!form) return;
  const payload = {
    title: form.title.value.trim(),
    description: form.description.value.trim(),
    objectives: form.objectives.value.trim(),
    technologies: form.technologies.value.trim(),
  };
  if (!payload.title) return toast("A project title is required.", "error");

  const response = await api.patch("/projects/me/", payload, { showErrors: false });
  if (!response.ok) {
    applyFieldErrors(form, response.data);
    if (response.data?.detail) toast(response.data.detail, "error");
    return;
  }
  toast("Project saved.", "success");
  loadMyProject();
}

/** Supervisor/admin: list projects to review. */
async function renderProjects() {
  const listRoot = document.getElementById("projectsList");
  listRoot.innerHTML = loadingBlock();

  const params = new URLSearchParams();
  params.set("page", projectsState.page);
  params.set("page_size", 10);
  const reviewStatus = document.getElementById("reviewStatusFilter")?.value;
  if (reviewStatus) params.set("review_status", reviewStatus);

  const response = await api.getPaged(`/projects/?${params.toString()}`);
  renderPager(document.getElementById("projectsPager"), response, (newPage) => {
    projectsState.page = newPage;
    renderProjects();
  });

  if (!response.results.length) {
    listRoot.innerHTML = emptyState("No projects match this filter.", "folder-git-2");
    return;
  }

  listRoot.innerHTML = `
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>Student</th><th>Title</th><th>Technologies</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${response.results.map((project) => `
            <tr>
              <td><strong>${escapeHtml(project.student_name)}</strong><br><span class="muted small">${escapeHtml(project.matric_number)}</span></td>
              <td>${escapeHtml(project.title)}</td>
              <td class="muted small">${escapeHtml(project.technologies || "-")}</td>
              <td>${statusBadge(project.review_status)}</td>
              <td class="flex flex-wrap">
                <button class="btn btn-ghost btn-sm" data-view="${project.id}"><i data-lucide="eye"></i>View</button>
                ${project.review_status === "submitted" && projectsState.role === "supervisor"
                  ? `<button class="btn btn-primary btn-sm" data-review="${project.id}"><i data-lucide="clipboard-check"></i>Review</button>`
                  : ""}
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
  refreshIcons();

  const byId = new Map(response.results.map((project) => [project.id, project]));
  listRoot.querySelectorAll("[data-view]").forEach((btn) =>
    btn.addEventListener("click", () => showProjectDetail(byId.get(Number(btn.dataset.view)))));
  listRoot.querySelectorAll("[data-review]").forEach((btn) =>
    btn.addEventListener("click", () => openProjectReviewDialog(byId.get(Number(btn.dataset.review)))));
}

/** Fetch one project from the list endpoints (no detail route exists). */
async function findProjectById(id) {
  const list = await apiGetList("/projects/?page_size=500");
  return list.find((project) => project.id === id) || null;
}

/** Read-only project detail modal. */
function showProjectDetail(project) {
  if (!project) return;
  openModal(`Project - ${escapeHtml(project.title)}`, `
    <table class="data-table">
      <tbody>
        <tr><th style="width:130px">Student</th><td>${escapeHtml(project.student_name)} (${escapeHtml(project.matric_number)})</td></tr>
        <tr><th>Title</th><td>${escapeHtml(project.title)}</td></tr>
        <tr><th>Status</th><td>${statusBadge(project.review_status)}</td></tr>
        <tr><th>Description</th><td>${escapeHtml(project.description || "-")}</td></tr>
        <tr><th>Objectives</th><td>${escapeHtml(project.objectives || "-")}</td></tr>
        <tr><th>Technologies</th><td>${escapeHtml(project.technologies || "-")}</td></tr>
        <tr><th>Submitted</th><td>${formatDateTime(project.submitted_at)}</td></tr>
        ${project.supervisor_comment ? `<tr><th>Supervisor</th><td>${escapeHtml(project.supervisor_name || "")}<br><em>${escapeHtml(project.supervisor_comment)}</em></td></tr>` : ""}
      </tbody>
    </table>`);
}

/** Supervisor approve / reject modal. */
function openProjectReviewDialog(project) {
  if (!project) return;
  const modal = openModal(`Review project - ${escapeHtml(project.student_name)}`, `
    <div class="form-note"><strong>Title:</strong> ${escapeHtml(project.title)}</div>
    <p class="small"><strong>Description:</strong> ${escapeHtml(project.description || "-")}</p>
    <p class="small"><strong>Objectives:</strong> ${escapeHtml(project.objectives || "-")}</p>
    <p class="small"><strong>Technologies:</strong> ${escapeHtml(project.technologies || "-")}</p>
    <div class="field">
      <label for="projReviewComment">Comment (required when rejecting)</label>
      <textarea id="projReviewComment" name="comment" placeholder="Write feedback for the student..."></textarea>
    </div>
    <div class="modal-actions">
      <span></span>
      <button class="btn btn-danger" id="projReject"><i data-lucide="x"></i>Reject</button>
      <button class="btn btn-primary" id="projApprove"><i data-lucide="check"></i>Approve</button>
    </div>`, { wide: true });
  modal.querySelector("#projReviewComment").focus();

  const sendReview = async (decision) => {
    const comment = modal.querySelector("#projReviewComment").value.trim();
    if (decision === "reject" && !comment) {
      return toast("A reason is required when rejecting.", "error");
    }
    const response = await api.post(`/projects/${project.id}/review/`, { decision, comment }, { showErrors: false });
    if (!response.ok) {
      toast(errorMessage(response.data), "error");
      return;
    }
    closeModal();
    toast(decision === "approve" ? "Project approved. The student has been notified." : "Project rejected. The student has been notified.", "success");
    renderProjects();
  };
  modal.querySelector("#projApprove").addEventListener("click", () => sendReview("approve"));
  modal.querySelector("#projReject").addEventListener("click", () => sendReview("reject"));
}
