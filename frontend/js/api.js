/* ==========================================================================
   SIWES Hub - api.js
   Thin wrapper around the Fetch API for talking to the Django REST backend.

   Every browser<->server call in SIWES Hub goes through these helpers so
   that CSRF handling, JSON parsing and error display stay consistent.
   ========================================================================== */

const API_BASE = "/api";

/** Global scopes for pages - populated by navigation.js (current user). */
window.APP = window.APP || {};

/**
 * Read a cookie value (we need the csrftoken cookie for writing requests).
 */
function getCookie(name) {
  const bits = document.cookie.split("; ");
  for (const bit of bits) {
    if (bit.startsWith(name + "=")) return decodeURIComponent(bit.slice(name.length + 1));
  }
  return null;
}

/** Make sure a CSRF cookie exists (session authentication needs one). */
async function ensureCsrfToken() {
  if (!getCookie("csrftoken")) {
    try {
      await fetch(`${API_BASE}/auth/csrf/`, { credentials: "same-origin" });
    } catch (error) {
      /* offline / server down: handled by the calling request */
    }
  }
  return getCookie("csrftoken");
}

/**
 * Core request helper. Never throws for handled API errors: it returns
 * {ok, status, data} so pages can decide how to react.
 */
async function apiRequest(method, path, body, options = {}) {
  const token = await ensureCsrfToken();
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && token) {
    headers["X-CSRFToken"] = token;
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
      ...options,
    });
  } catch (error) {
    // Network failure (server stopped, offline...)
    return { ok: false, status: 0, data: { detail: "Could not reach the server. Is it running?" } };
  }

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (error) {
      data = { detail: text.slice(0, 200) };
    }
  }
  const ok = response.status >= 200 && response.status < 300;
  if (!ok && options.showErrors !== false) {
    toast(errorMessage(data), "error");
  }
  return { ok, status: response.status, data };
}

/** Turn DRF error payloads into one readable line. */
function errorMessage(data) {
  if (!data) return "Something went wrong.";
  if (typeof data.detail === "string") return data.detail;
  if (typeof data === "string") return data;
  const parts = [];
  for (const [key, value] of Object.entries(data)) {
    parts.push(`${key.replace(/_/g, " ")}: ${Array.isArray(value) ? value.join(", ") : value}`);
  }
  return parts.join(" · ") || "Something went wrong.";
}

/* Shorthand helpers used by every page script. */
const api = {
  get: (path, options) => apiRequest("GET", path, undefined, options),
  post: (path, body, options) => apiRequest("POST", path, body, options),
  patch: (path, body, options) => apiRequest("PATCH", path, body, options),
  put: (path, body, options) => apiRequest("PUT", path, body, options),
  del: (path, options) => apiRequest("DELETE", path, undefined, options),
  /** List endpoint without pagination awareness. */
  getList: apiGetList,
  /** List endpoint normalising {results, count, pages}. */
  getPaged: apiGetPaged,
};

/**
 * GET a list endpoint. Lists without ?page= return plain arrays; with
 * ?page= they return {count, pages, results}. This normalises both.
 */
async function apiGetList(path) {
  const response = await api.get(path, { showErrors: false });
  if (!response.ok) return [];
  const data = response.data;
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

/**
 * GET a list with pagination awareness: resolves {results, count, pages}
 * when the backend paginates, otherwise {results, count, pages: 1}.
 */
async function apiGetPaged(path) {
  const response = await api.get(path, { showErrors: false });
  if (!response.ok) return { results: [], count: 0, pages: 0, page: 1 };
  const data = response.data;
  if (Array.isArray(data)) return { results: data, count: data.length, pages: 0, page: 1 };
  if (data && Array.isArray(data.results)) return { results: data.results, count: data.count ?? 0, pages: data.pages ?? 0, page: data.page ?? 1 };
  return { results: [], count: 0, pages: 0, page: 1 };
}

/* ------------------------------------------------------------------ */
/* Toast notifications                                                  */
/* ------------------------------------------------------------------ */
function ensureToastContainer() {
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  return container;
}

/** Show a short-lived message. type: "success" | "error" | "info" */
function toast(message, type = "info") {
  const icons = { success: "check-circle", error: "alert-circle", info: "info" };
  const element = document.createElement("div");
  element.className = `toast ${type}`;
  element.innerHTML = `<i data-lucide="${icons[type] || "info"}"></i><span></span>`;
  element.querySelector("span").textContent = message;
  ensureToastContainer().appendChild(element);
  refreshIcons();
  setTimeout(() => element.remove(), 3800);
}

/* ------------------------------------------------------------------ */
/* Lucide icons                                                         */
/* ------------------------------------------------------------------ */
(function () {
  const script = document.createElement("script");
  script.src = "/assets/vendor/lucide.min.js";
  script.onload = () => {
    window.LucideReady = lucide.createIcons;
    refreshIcons();
  };
  script.onerror = () => {
    // Icons are decorative: the app must still work without them.
    window.LucideReady = () => {};
  };
  document.head.appendChild(script);
})();

/** (Re)render all <i data-lucide="..."> elements as real SVG icons. */
function refreshIcons() {
  if (window.lucide && window.lucide.createIcons) {
    window.lucide.createIcons();
  }
}

/* ------------------------------------------------------------------ */
/* Small formatting helpers                                             */
/* ------------------------------------------------------------------ */
function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatDateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function statusBadge(status) {
  const text = String(status ?? "").replace(/_/g, " ");
  const known = ["draft", "submitted", "approved", "rejected", "late", "absent", "excused", "present",
    "active", "inactive", "in_progress", "completed", "not_submitted", "pending"];
  const cls = known.includes(text) ? `badge-${text}` : "badge-neutral";
  return `<span class="badge ${cls}">${escapeHtml(text || "-")}</span>`;
}
