

## `CLAUDE.md`

```markdown
# CLAUDE.md - Project Dashboard Frontend

## Context
This file extends the main project description, "Task.txt" (provided separately)
Read that first. This file covers only the frontend task.

## Your task
Build a minimal single-page frontend that consumes the existing REST API.
No backend changes. No framework required - plain HTML + CSS + JS is Required
for simplicity.
## API base URL
Read from a single constant at the top of your JS file:
```javascript
const API_BASE = window.location.origin; // same host, API served on same EC2
```

## Pages / views required

### 1. Login / Register
- Toggle between login and register forms on the same page
- Register: login, password, repeat_password fields
- Login: login, password fields
- On success: store JWT in localStorage, redirect to dashboard
- On error: show the API error message inline (do not alert())

### 2. Dashboard - project list
- GET /projects on load
- Show each project as a card: name, description, document count
- "New project" button -> inline form (name, description) -> POST /projects
- Click a project card -> open project detail view

### 3. Project detail view
- Show project name, description
- Show documents list (filename, size if available)
- Upload document button -> file picker (PDF/DOCX only) -> POST /project/{id}/documents
- Download button per document -> GET /document/{id} -> open presigned URL in new tab
- Invite user button (owner only) -> input login -> POST /project/{id}/invite?user={login}
- Delete project button (owner only) -> DELETE /project/{id} -> back to dashboard
- Delete document button (owner only) -> DELETE /document/{id}

## Auth
- Every request (except POST /auth and POST /login) must include:
  `Authorization: Bearer <token>` header
- If any request returns 401 -> clear localStorage -> redirect to login page
- Token is stored in localStorage under the key `access_token`

## What "minimal" means
- No build step required (no webpack, no bundler)
- Single HTML file is fine, or split into index.html + app.js + style.css
- No UI component libraries - plain CSS only
- Must be functional, not pretty. Clean layout, readable, mobile is not required

## File placement
```
frontend/
├── index.html
├── app.js
└── style.css
```
Served as static files from EC2 (nginx or the FastAPI static mount).

## Role awareness
- After login, decode the JWT payload (base64 middle segment) to get `user_id`
- When viewing a project, check if current user is owner:
  GET /project/{id}/info returns the project - compare `owner_id` with stored `user_id`
- Show delete / invite controls only if `user_id === project.owner_id`

## API error handling rules
- 401 -> logout and redirect to login
- 403 -> show "You don't have permission for this action"
- 404 -> show "Not found"
- 422 -> extract and show `detail` array from response body
- 500 -> show "Server error, try again later"

## What to produce
1. The three files above (index.html, app.js, style.css)
2. A short note in README.md under a ## Frontend section explaining:
   - how to serve it locally (python -m http.server or nginx)
   - how it is served on EC2

## What NOT to do
- Do not modify any backend files
- Do not add new API endpoints
- Do not add npm / package.json / node_modules
- Do not use any CSS framework (Bootstrap, Tailwind, etc.)
- Do not use fetch polyfills - modern browsers only
```