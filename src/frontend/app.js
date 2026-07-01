'use strict';

/* Config*/
const API_BASE = window.location.origin; // same host, API served on same EC2
const TOKEN_KEY = 'access_token';

/* Utilities */

// Escapes special characters to prevent XSS when rendering user input directly into HTML
function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// Converts a raw byte count into a clean, human-readable string (eg. 2.5 MB)
function formatBytes(bytes) {
  if (bytes == null || Number.isNaN(bytes)) return '';
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

// Extracts and parses the JSON payload from a standard JWT token (base64url decode)
function decodeJwt(token) {
  try {
    const payload = token.split('.')[1];
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join('')
    );
    return JSON.parse(json);
  } catch (e) {
    return null;
  }
}

// Extracts user_id from JWT payload (matches backend's create_access_token):
// { "sub": "<user_id>", "exp": <unix_timestamp> }
function getUserIdFromToken(token) {
  const payload = decodeJwt(token);
  if (!payload) return null;
  return payload.sub ? parseInt(payload.sub, 10) : null;
}

// Standardizes document array shape - backend may return raw array or {documents: [...]} wrapper
function extractDocuments(res) {
  return Array.isArray(res) ? res : (res && res.documents) || [];
}

/* 
 * In-memory state (token is also persisted to localStorage for session persistence)
 * Initialized once at page load to restore session if browser was closed/reopened */
const initialToken = localStorage.getItem(TOKEN_KEY) || null;
const state = {
  token: initialToken,
  userId: initialToken ? getUserIdFromToken(initialToken) : null,
  projects: [], 
};

/* Auth state helpers */

// Stores a new JWT in localStorage and memory, then decodes and caches the user's ID
function setToken(token) {
  state.token = token;
  localStorage.setItem(TOKEN_KEY, token);
  state.userId = getUserIdFromToken(token);
}

// Cleans up all credentials and session details to sign the user out
function clearToken() {
  state.token = null;
  state.userId = null;
  localStorage.removeItem(TOKEN_KEY);
}

// Simple check to verify if an active session token is loaded in memory
function isLoggedIn() {
  return !!state.token;
}

/* API layer */

// Custom error class to carry HTTP status codes alongside API rejection details
class ApiError extends Error {
  constructor(status, message, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

// Central fetch wrapper: handles content-type negotiation, JWT header attachment, network errors, and 401 redirects
// Catches both network failures (fetch error) and HTTP error responses; parses Pydantic validation errors (422) into readable messages
async function apiFetch(path, { method = 'GET', body, isForm = false } = {}) {
  const headers = {};
  let reqBody = undefined;

  if (body !== undefined) {
    if (isForm) {
      reqBody = body; // Let the browser set multipart/form-data boundaries automatically
    } else {
      headers['Content-Type'] = 'application/json';
      reqBody = JSON.stringify(body);
    }
  }

  // Attach JWT Bearer token to all non-auth endpoints (backend to verify user identity and check permissions)
  const isAuthRoute = path.startsWith('/auth') || path.startsWith('/login');
  if (state.token && !isAuthRoute) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  let res;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers,
      body: reqBody,
    });
  } catch (networkErr) {
    // Network failure (no connection, CORS blocked, etc.)
    throw new ApiError(0, 'Network error - check your connection and try again.');
  }

  // 401 means JWT is expired or invalid - clear session and force re-login
  if (res.status === 401) {
    clearToken();
    navigate('/login');
    throw new ApiError(401, 'Session expired. Please log in again.');
  }

  if (!res.ok) {
    const contentType = res.headers.get('content-type') || '';
    let detail;
    let message;

    // Try to extract error detail from JSON response
    if (contentType.includes('application/json')) {
      const data = await res.json().catch(() => null);
      detail = data && data.detail;
    }

    // Parse Pydantic validation errors (422 status) into field-level messages
    if (res.status === 422 && Array.isArray(detail)) {
      message = detail.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ');
    } else if (res.status === 403) {
      message = "You don't have permission for this action.";
    } else if (res.status === 404) {
      message = 'Not found.';
    } else if (res.status === 500) {
      message = 'Server error, try again later.';
    } else if (typeof detail === 'string') {
      message = detail;
    } else {
      message = `Request failed (${res.status}).`;
    }

    throw new ApiError(res.status, message, detail);
  }

  return res;
}

// Wrapper for apiFetch that automatically parses and returns JSON if the response has content; returns null for 204 No Content
async function apiJson(path, opts) {
  const res = await apiFetch(path, opts);
  if (res.status === 204) return null;
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) return res.json();
  return null;
}

// Downloads a document: if backend returns presigned S3 URL (as JSON), open it directly; otherwise proxy file bytes through browser blob download
async function downloadDocument(docId, suggestedName) {
  const res = await apiFetch(`/document/${docId}`);
  const contentType = res.headers.get('content-type') || '';

  // Backend response is a presigned S3 URL - let browser download directly from S3
  if (contentType.includes('application/json')) {
    const data = await res.json();
    const url = data.url || data.download_url || data.presigned_url;
    if (url) {
      window.open(url, '_blank', 'noopener');
      return;
    }
    throw new ApiError(500, 'Download URL missing from server response.');
  }

  // Backend response is raw file bytes - create blob and trigger browser download
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = suggestedName || 'document';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(blobUrl);
}

/* Router */

// Programmatically changes the URL hash to trigger a page transition (SPA navigation model)
function navigate(path) {
  if (location.hash.slice(1) !== path) {
    location.hash = path; // Triggers 'hashchange' event, which calls render()
  } else {
    render(); // Force re-render if hash hasn't changed
  }
}

// Returns the current route based on URL hash; defaults to '/login' if hash is empty
function currentRoute() {
  return location.hash.slice(1) || '/login';
}

// Master router: enforces auth state guards (can't access protected routes without token), shows/hides topbar, and dispatches to view functions
function render() {
  const route = currentRoute();
  const topbar = document.getElementById('topbar');

  // unauthenticated user trying to access protected route - redirect to login
  if (!isLoggedIn() && route !== '/login') {
    location.hash = '/login';
    return;
  }
  // authenticated user trying to access login - redirect to dashboard (already logged in)
  if (isLoggedIn() && route === '/login') {
    location.hash = '/dashboard';
    return;
  }

  topbar.hidden = !isLoggedIn();
  if (isLoggedIn()) {
    document.getElementById('currentUserLabel').textContent =
      state.userId != null ? `user #${state.userId}` : '';
  }

  // Route dispatch
  if (route === '/login') return renderLogin();
  if (route === '/dashboard') return renderDashboard();

  const match = route.match(/^\/project\/([^/]+)$/);
  if (match) return renderProjectDetail(match[1]);

  return renderNotFound();
}

window.addEventListener('hashchange', render); // Trigger render on hash change (navigation)
window.addEventListener('DOMContentLoaded', render); // Trigger render on initial page load

document.getElementById('logoutBtn').addEventListener('click', () => {
  clearToken();
  navigate('/login');
});

/* View: Login / Register */

// Renders the auth card with login/register tabs; handles form submissions for both flows
// Login: POST /login - get JWT - setToken - redirect to dashboard
// Register: POST /auth - show success message - user can then log in
function renderLogin() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="auth-wrap">
      <div class="auth-card">
        <h1>Project Dashboard</h1>
        <div class="tabs">
          <button class="tab-btn active" data-tab="login" type="button">Log in</button>
          <button class="tab-btn" data-tab="register" type="button">Register</button>
        </div>
        <div class="error-banner" id="authError" hidden></div>
        <div class="notice" id="authNotice" hidden></div>

        <form id="loginForm" class="auth-form">
          <label>Login
            <input name="login" type="text" required autocomplete="username">
          </label>
          <label>Password
            <input name="password" type="password" required autocomplete="current-password">
          </label>
          <button type="submit" class="btn btn-primary">Log in</button>
        </form>

        <form id="registerForm" class="auth-form" hidden>
          <label>Login
            <input name="login" type="text" required autocomplete="username">
          </label>
          <label>Password
            <input name="password" type="password" required autocomplete="new-password">
          </label>
          <label>Repeat password
            <input name="repeat_password" type="password" required autocomplete="new-password">
          </label>
          <button type="submit" class="btn btn-primary">Create account</button>
        </form>
      </div>
    </div>
  `;

  const errorEl = document.getElementById('authError');
  const noticeEl = document.getElementById('authNotice');
  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  const tabs = app.querySelectorAll('.tab-btn');

  function showError(msg) { errorEl.textContent = msg; errorEl.hidden = false; noticeEl.hidden = true; }
  function hideMessages() { errorEl.hidden = true; noticeEl.hidden = true; }

  // Tab switching UI
  tabs.forEach((btn) => btn.addEventListener('click', () => {
    tabs.forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    hideMessages();
    const tab = btn.dataset.tab;
    loginForm.hidden = tab !== 'login';
    registerForm.hidden = tab !== 'register';
  }));

  // Login form: send credentials, extract JWT from response, cache it
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideMessages();
    const fd = new FormData(loginForm);
    const payload = { login: fd.get('login'), password: fd.get('password') };
    try {
      const data = await apiJson('/login', { method: 'POST', body: payload });
      const token = data && (data.access_token || data.token || data.jwt);
      if (!token) throw new ApiError(500, 'Login succeeded but no token was returned.');
      setToken(token); // Cache JWT in state & localStorage
      navigate('/dashboard');
    } catch (err) {
      showError(err.message);
    }
  });

  // Register form: send new user credentials, show success, let user switch to login tab
  registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideMessages();
    const fd = new FormData(registerForm);
    const payload = {
      login: fd.get('login'),
      password: fd.get('password'),
      repeat_password: fd.get('repeat_password'),
    };
    try {
      await apiJson('/auth', { method: 'POST', body: payload });
      noticeEl.textContent = 'Account created. You can log in now.';
      noticeEl.hidden = false;
      tabs[0].click(); // Switch to login tab
      loginForm.elements.login.value = payload.login; // Pre-fill login field
    } catch (err) {
      showError(err.message);
    }
  });
}

/* View: Dashboard (project list) */

// Renders the workspace dashboard: fetches user's projects (all accessible to them as owner or participant),
// displays grid of cards (owner/participant badge, doc count), and provides modal to create new project
async function renderDashboard() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="dash">
      <div class="dash-header">
        <h1>Your projects</h1>
        <button id="newProjectBtn" class="btn btn-primary" type="button">+ New project</button>
      </div>
      <form id="newProjectForm" class="card form-card" hidden>
        <label>Name <input name="name" required maxlength="120"></label>
        <label>Description <textarea name="description" rows="2"></textarea></label>
        <div class="form-actions">
          <button type="submit" class="btn btn-primary">Create</button>
          <button type="button" id="cancelNewProject" class="btn btn-ghost">Cancel</button>
        </div>
      </form>
      <div class="error-banner" id="dashError" hidden></div>
      <div id="projectGrid" class="project-grid"><p class="muted">Loading projects…</p></div>
    </div>
  `;

  const newBtn = document.getElementById('newProjectBtn');
  const newForm = document.getElementById('newProjectForm');
  const cancelBtn = document.getElementById('cancelNewProject');
  const errorEl = document.getElementById('dashError');
  const grid = document.getElementById('projectGrid');

  function showError(msg) { errorEl.textContent = msg; errorEl.hidden = false; }

  newBtn.addEventListener('click', () => { newForm.hidden = false; newBtn.hidden = true; });
  cancelBtn.addEventListener('click', () => { newForm.hidden = true; newBtn.hidden = false; newForm.reset(); });

  // Create new project form: POST /projects with name and description, then refresh list
  newForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(newForm);
    const payload = { name: fd.get('name'), description: fd.get('description') };
    try {
      await apiJson('/projects', { method: 'POST', body: payload });
      newForm.reset();
      newForm.hidden = true;
      newBtn.hidden = false;
      await loadProjects(); // Refresh project list to show new project
    } catch (err) {
      showError(err.message);
    }
  });

  // Render projects grid: display card for each, show owner vs. participant badge, attach click handler to navigate to detail
  function renderGrid() {
    if (state.projects.length === 0) {
      grid.innerHTML = '<p class="muted">No projects yet. Create your first one above.</p>';
      return;
    }
    grid.innerHTML = '';

    state.projects.forEach((p) => {
      const isOwner = state.userId != null && String(p.owner_id) === String(state.userId);
      const docCount = Array.isArray(p.documents) ? p.documents.length : (p.document_count ?? 0);

      const card = document.createElement('button');
      card.className = 'card project-card';
      card.type = 'button';
      card.dataset.id = String(p.id);

      const cardTop = document.createElement('div');
      cardTop.className = 'card-top';

      const title = document.createElement('h3');
      title.textContent = p.name || '';

      const badge = document.createElement('span');
      badge.className = `badge ${isOwner ? 'badge-owner' : 'badge-participant'}`;
      badge.textContent = isOwner ? 'Owner' : 'Participant';

      const description = document.createElement('p');
      description.className = 'card-desc';
      description.textContent = p.description || 'No description';

      const meta = document.createElement('p');
      meta.className = 'card-meta';
      meta.textContent = `${docCount} document${docCount === 1 ? '' : 's'}`;

      cardTop.append(title, badge);
      card.append(cardTop, description, meta);
      card.addEventListener('click', () => navigate(`/project/${card.dataset.id}`));
      grid.appendChild(card);
    });
  }

  // Fetch all projects accessible to current user (backend returns only those the user owns or is invited to)
  async function loadProjects() {
    try {
      const projects = await apiJson('/projects');
      state.projects = Array.isArray(projects) ? projects : [];
      renderGrid();
    } catch (err) {
      grid.innerHTML = '';
      showError(err.message);
    }
  }

  await loadProjects();
}

/* View: Project detail */

// Renders a single project's detail page: project info (editable if owner), documents list/upload, and invite form (owner-only)
// role-based UI: owner sees delete/invite buttons, participant sees read-only info but can download/modify docs
async function renderProjectDetail(id) {
  const app = document.getElementById('app');
  app.innerHTML = '<p class="muted">Loading project…</p>';

  let project;
  let documents;
  try {
    project = await apiJson(`/project/${id}/info`);
    const docsRes = await apiJson(`/project/${id}/documents`);
    documents = extractDocuments(docsRes);
  } catch (err) {
    app.innerHTML = `
      <div class="error-banner">${escapeHtml(err.message)}</div>
      <button id="backBtn" class="btn btn-ghost" type="button">&larr; Back to projects</button>
    `;
    document.getElementById('backBtn').addEventListener('click', () => navigate('/dashboard'));
    return;
  }

  // rolechecl, is current user the project owner
  const isOwner = state.userId != null && String(project.owner_id) === String(state.userId);

  app.innerHTML = `
    <div class="project-detail">
      <button id="backBtn" class="btn btn-ghost" type="button">&larr; Back to projects</button>
      <div class="error-banner" id="detailError" hidden></div>
      <div class="notice" id="detailNotice" hidden></div>

      <section class="card">
        <div class="card-top">
          <span class="badge ${isOwner ? 'badge-owner' : 'badge-participant'}">${isOwner ? 'Owner' : 'Participant'}</span>
          ${isOwner ? '<button id="deleteProjectBtn" class="btn btn-danger" type="button">Delete project</button>' : ''}
        </div>
        <form id="infoForm">
          <label>Name <input name="name" value="" required maxlength="120"></label>
          <label>Description <textarea name="description" rows="3"></textarea></label>
          <button type="submit" class="btn btn-primary">Save changes</button>
        </form>
      </section>

      <section class="card">
        <div class="card-top"><h2>Documents</h2></div>
        <form id="uploadForm" class="upload-form">
          <input type="file" name="files" accept=".pdf,.docx" multiple required>
          <button type="submit" class="btn btn-primary">Upload</button>
        </form>
        <ul id="docList" class="doc-list"></ul>
      </section>

      ${isOwner ? `
      <section class="card">
        <div class="card-top"><h2>Invite a user</h2></div>
        <form id="inviteForm" class="invite-form">
          <input name="user" placeholder="Login to invite" required>
          <button type="submit" class="btn btn-primary">Grant access</button>
        </form>
      </section>` : ''}
    </div>
  `;

  const errorEl = document.getElementById('detailError');
  const noticeEl = document.getElementById('detailNotice');
  function showError(msg) { errorEl.textContent = msg; errorEl.hidden = false; noticeEl.hidden = true; }
  function showNotice(msg) { noticeEl.textContent = msg; noticeEl.hidden = false; errorEl.hidden = true; }

  document.getElementById('backBtn').addEventListener('click', () => navigate('/dashboard'));

  const infoForm = document.getElementById('infoForm');
  infoForm.elements.name.value = project.name || '';
  infoForm.elements.description.value = project.description || '';

  // Edit project info: PUT /project/{id}/info with name and description
  infoForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = { name: fd.get('name'), description: fd.get('description') };
    try {
      const updated = await apiJson(`/project/${id}/info`, { method: 'PUT', body: payload });
      project = updated || project;
      showNotice('Saved.');
    } catch (err) {
      showError(err.message);
    }
  });

  // Owner only: delete project (and all its documents from DB + S3)
  if (isOwner) {
    document.getElementById('deleteProjectBtn').addEventListener('click', async () => {
      if (!confirm(`Delete "${escapeHtml(project.name)}"? This also deletes its documents. This cannot be undone.`)) return;
      try {
        await apiFetch(`/project/${id}`, { method: 'DELETE' });
        navigate('/dashboard');
      } catch (err) {
        showError(err.message);
      }
    });

    // Owner only: invite a user to access this project (grant participant role)
    document.getElementById('inviteForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const login = fd.get('user');
      try {
        await apiFetch(`/project/${id}/invite?user=${encodeURIComponent(login)}`, { method: 'POST' });
        showNotice(`Invited "${login}".`);
        e.target.reset();
      } catch (err) {
        showError(err.message);
      }
    });
  }

  // extract document display name (fallback chain for different backend response shapes)
  function docName(doc) { return doc.filename || doc.name || doc.file_name || `Document ${doc.id}`; }
  
  // format document file size for display
  function docSize(doc) {
    const bytes = doc.size_bytes ?? doc.size ?? null;
    return bytes != null ? formatBytes(bytes) : '';
  }

  // Render documents list: show name, size, and action buttons (download for all, delete for owner only)
  function renderDocs() {
    const list = document.getElementById('docList');
    if (documents.length === 0) {
      list.innerHTML = '<li class="muted">No documents yet. Upload one above.</li>';
      return;
    }
    list.innerHTML = documents.map((doc) => `
      <li class="doc-row" data-id="${escapeHtml(String(doc.id))}">
        <span class="doc-name">${escapeHtml(docName(doc))}</span>
        <span class="doc-size mono">${escapeHtml(docSize(doc))}</span>
        <span class="doc-actions">
          <button class="btn btn-ghost doc-download" type="button">Download</button>
          ${isOwner ? '<button class="btn btn-danger doc-delete" type="button">Delete</button>' : ''}
        </span>
      </li>
    `).join('');

    // Attach handlers to each document row
    list.querySelectorAll('.doc-row').forEach((row) => {
      const docId = row.dataset.id;
      const doc = documents.find((d) => String(d.id) === docId);

      // Download document: GET /document/{id} - presigned URL or blob
      row.querySelector('.doc-download').addEventListener('click', async () => {
        try {
          await downloadDocument(docId, docName(doc));
        } catch (err) {
          showError(err.message);
        }
      });

      // Owner only: delete document from project (also removes from S3)
      const delBtn = row.querySelector('.doc-delete');
      if (delBtn) {
        delBtn.addEventListener('click', async () => {
          if (!confirm(`Delete "${docName(doc)}"?`)) return;
          try {
            await apiFetch(`/document/${docId}`, { method: 'DELETE' });
            documents = documents.filter((d) => String(d.id) !== docId);
            renderDocs();
          } catch (err) {
            showError(err.message);
          }
        });
      }
    });
  }
  renderDocs();

  // Upload documents: POST /project/{id}/documents with multipart FormData, then refresh document list
  document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = e.target.elements.files;
    const files = Array.from(input.files || []);
    if (files.length === 0) return;

    // Validate file types on client (PDF and DOCX only, matches backend acceptance)
    const allowed = /\.(pdf|docx)$/i;
    const bad = files.find((f) => !allowed.test(f.name));
    if (bad) {
      showError(`"${bad.name}" is not a PDF or DOCX file.`);
      return;
    }

    const fd = new FormData();
    files.forEach((f) => fd.append('files', f));
    try {
      await apiFetch(`/project/${id}/documents`, { method: 'POST', body: fd, isForm: true });
      const refreshed = await apiJson(`/project/${id}/documents`);
      documents = extractDocuments(refreshed);
      renderDocs();
      e.target.reset();
      showNotice('Uploaded.');
    } catch (err) {
      showError(err.message);
    }
  });
}

/* View: 404 */

// Fallback for invalid routes: show error card and link back to dashboard
function renderNotFound() {
  document.getElementById('app').innerHTML = `
    <div class="card">
      <p>Page not found.</p>
      <button id="homeBtn" class="btn btn-primary" type="button">Go to dashboard</button>
    </div>
  `;
  document.getElementById('homeBtn').addEventListener('click', () => navigate('/dashboard'));
}