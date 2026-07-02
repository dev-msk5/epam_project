# Project Dashboard - README

---

## Table of Contents
1. [Overview](#overview)
2. [Setup & Run Locally](#setup--run-locally)
3. [Architecture Overview](#architecture-overview)
4. [Data Model](#data-model)
5. [Auth & Authorization Flow](#auth--authorization-flow)
6. [Documents, Storage & Quota Enforcement](#documents-storage--quota-enforcement)
7. [AWS Setup](#aws-setup)
8. [Frontend](#frontend)
9. [API Reference](#api-reference)
10. [Key Design Decisions](#key-design-decisions)
11. [CI Pipeline](#ci-pipeline)
12. [Running Tests](#running-tests)
13. [Environment Variables Reference](#environment-variables-reference)
14. [Known Gaps / TODO](#known-gaps--todo)

---

## Overview

A backend service for managing projects and their documents. Users can create projects, upload documents (PDF/DOCX), and share access with other users. Files are stored in AWS S3; an AWS Lambda function tracks storage usage per project and enforces a hard quota. A minimal vanilla-JS frontend is bundled and served by the same FastAPI app.

**Stack:**
- Python 3.12+ (CI/Docker currently run on 3.13), FastAPI
- PostgreSQL + SQLAlchemy (async, via `asyncpg`)
- Docker + docker-compose
- AWS S3 (file storage) + AWS Lambda (S3 event processing) + optional AWS SSM Parameter Store (production config)
- GitHub Actions (lint → test → build & push)

---

## Setup & Run Locally

### Prerequisites
- Docker + docker-compose
- AWS account with an S3 bucket and credentials (only required for document upload/download; the rest of the API works without AWS configured)

### 1. Clone the repository
```bash
git clone https://github.com/dev-msk5/epam_project.git
cd epam_project
```

### 2. Create `.env` file
```bash
cp _.env.example.txt .env
```

`docker-compose.yml` only injects `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and the SSM toggle vars directly as environment variables - everything else (`DATABASE_URL`, `SECRET_KEY`, AWS credentials, etc.) is read by the app from the `.env` file itself, which is mounted into the container via the `.:/app` bind volume. Make sure `.env` lives at the project root and that `DATABASE_URL` matches the `DB_*` values you set:

```env
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=dashboard

DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/dashboard
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
S3_BUCKET_NAME=your-bucket-name
AWS_REGION=us-east-1
PROJECT_STORAGE_LIMIT_BYTES=524288000

# Optional - EC2/production only, loads config from SSM Parameter Store instead of .env
USE_SSM=false
```

### 3. Run with Docker
```bash
docker-compose up --build
```

The app (API + frontend) is available at `http://localhost:8000`. In the bundled `docker-compose.yml`, the app container runs with `--reload` disabled off the base command already - remove `- .:/app` from `volumes` for a production-style build using the baked image instead of live-syncing local files.

### 4. API Docs
```
http://localhost:8000/docs      # Swagger UI
http://localhost:8000/redoc     # ReDoc
```

---

## Architecture Overview

```
Browser (vanilla JS SPA, served by FastAPI at "/")
  │
  ▼
FastAPI (Docker container)
  │
  ├── PostgreSQL (docker-compose service)
  │     └── users, projects, documents, access
  │
  └── AWS S3 (file storage)
        │
        └── S3 ObjectCreated event
                │
                ▼
          AWS Lambda (lambda_s3_handler.py)
                │
                ├── sums actual object sizes under projects/{id}/documents/
                └── deletes the newly-created object if the project exceeds quota
```

**Request flow:**
1. Client sends a JWT-authenticated request (`Authorization: Bearer <token>`)
2. FastAPI decodes the token to get `user_id`
3. The service layer resolves the caller's role for the target project (`owner` / `participant` / 403) before doing anything else
4. Files are streamed directly to S3 - never persisted to the container filesystem
5. On upload, S3 fires an `ObjectCreated` event that invokes the Lambda, which independently re-verifies the project's true storage usage from S3 and deletes the file if it caused the project to exceed quota

---

## Data Model

```
users
├── id                  PK
├── login               unique, min 8 chars
└── hashed_password

projects
├── id                  PK
├── name
└── description
    (no owner_id column - ownership is derived entirely from `access.role == 'owner'`)

documents
├── id                  PK
├── name                sanitized filename
├── url                 S3 key
├── size                bytes
├── is_pending          upload/replace in-progress flag
├── project_id          FK → projects.id
└── owner_id            FK → users.id (uploader, informational - not used for access checks)

access
├── id                  PK
├── project_id          FK → projects.id
├── user_id             FK → users.id
└── role                'owner' | 'participant'  (CHECK constraint)
```

### Normalization rationale
- **`access`** is a normalized join table for project membership (many-to-many users↔projects with a role attribute) and is now the **only** place ownership is recorded - `projects` has no `owner_id` column at all. This avoids having two competing sources of truth for "who owns this" (a column on `projects` plus a row in `access`) that could drift out of sync; there's exactly one place role lives, and it keeps 2NF/3NF instead of scanning an array/JSON column on `projects`.
- **`documents.url`** stores the S3 **key**, not a full URL - presigned download URLs are generated on demand (15-minute expiry), so the DB stays region/bucket-rename agnostic.
- **`documents.is_pending`** is a deliberate denormalization: it lets the API mark a row as "in flight" the moment the DB insert happens (before the S3 upload completes) so a crash mid-upload doesn't leave an invisible or half-uploaded file visible to `GET`/`download`. The alternative (a separate `uploads` table) was judged unnecessary complexity for this project's scale.
- **`documents.size`** is cached on the row instead of derived live from S3 on every request. This is a performance-motivated denormalization: quota checks run on every upload/replace and would otherwise need an S3 `ListObjects` call each time. The Lambda periodically re-derives the real total from S3 as the source of truth and corrects drift (see [Documents, Storage & Quota Enforcement](#documents-storage--quota-enforcement)).

### ORM vs raw SQL
SQLAlchemy async ORM (2.0-style, `Mapped`/`mapped_column`) is used throughout. A raw-SQL equivalent of the core access check (`ProjectService._resolve_access`) would be:
```sql
SELECT role FROM access
WHERE project_id = $1 AND user_id = $2;
```
ORM advantage here: relationship loading (`selectinload`), row locking (`with_for_update()`) and cascades are expressed declaratively and stay consistent with the migration-generating models. Raw SQL advantage: no ORM identity-map surprises, and the query shape is guaranteed rather than inferred.

---

## Auth & Authorization Flow

### Registration (`POST /auth`)
- `login` and `password` must each be ≥ 8 characters; `password` must contain at least one letter and one digit; `repeat_password` must match `password` (all enforced by Pydantic validators before the request reaches the DB).
- Login uniqueness is checked, then re-checked via `IntegrityError` handling to close the race window between two concurrent registrations with the same login (both return `409`).
- Passwords are hashed with **Argon2** (`pwdlib`, with bcrypt registered as a fallback verifier).

### Login (`POST /login`)
1. Credentials are verified against the stored Argon2 hash.
2. A JWT is issued containing `{"sub": "<user_id>", "exp": <1 hour from now>}`.
3. All subsequent requests must send `Authorization: Bearer <token>`.

### Role enforcement
Two roles exist, resolved per-project by `ProjectService._resolve_access`:

| Role | Permissions |
|------|-------------|
| `owner` | Full access - read, update, delete project, delete/replace/upload documents, invite users, generate share links |
| `participant` | Read + update project info, upload/list/download/replace documents - **cannot** delete the project or delete documents |

- Ownership has **no separate column on `projects`** - a project's owner is whoever holds the `owner` row for that `project_id` in `access`. The `owner` row is written at project-creation time in the same transaction as the project itself, so `access` is the single source of truth for role, with no second field to keep in sync.
- Every role - `owner` or `participant` - is resolved the same way: a lookup against `access` for `(project_id, user_id)`.
- Every project/document endpoint calls the same `_resolve_access` resolver - there's a single source of truth for permission checks, not per-route logic.
- No access row and not the owner → `403`. Nonexistent project → `404`.

### Access check flow
```
Request → decode JWT → user_id
  → look up Access(project_id, user_id)
      → found → role = row.role   ("owner" or "participant")
      → not found → 403 Forbidden
  → (if the action requires owner and role != "owner") → 403 Forbidden
```

---

## Documents, Storage & Quota Enforcement

Quota enforcement is **two-layered**, not purely observational:

1. **Synchronous, in the API (source of "should this request even happen")** - `DocumentService` locks the project row with `SELECT ... FOR UPDATE` before computing `used = SUM(documents.size)` for the project. If `used + incoming_size(s) > PROJECT_STORAGE_LIMIT_BYTES`, the request is rejected with `413` **before** anything is written to S3 or committed to the DB. The row lock serializes concurrent uploads to the same project so two parallel requests can't both pass a stale quota check.
2. **Asynchronous, in Lambda (source of truth / drift correction)** - on every S3 `ObjectCreated` event, the Lambda re-sums the *actual* object sizes under `projects/{project_id}/documents/` directly from S3 (not from the DB) and **deletes the just-created object** if the real total exceeds `PROJECT_STORAGE_LIMIT_BYTES`. This catches any case where the DB-cached `size` column drifted from reality (e.g. partial failures, manual bucket edits, bugs in the sync check) - it is a backstop, not the primary gate.

Other document-handling details:
- Only `.pdf` and `.docx` are accepted; extension is checked both client-side (JS) and twice server-side (route-level `_validate_file_types` and service-level `_safe_filename`).
- `_safe_filename` strips path separators, rejects hidden/empty names, and whitelists `[a-zA-Z0-9._-]` in the base name - this blocks path-traversal and injection via uploaded filenames.
- S3 key format: `projects/{project_id}/documents/{document_id}_{upload_or_replace_id}_{sanitized_filename}` - a fresh random id is embedded on every upload/replace so keys never collide and Lambda can always parse `project_id` back out via regex.
- On `PUT /document/{id}`, **any** project member (owner or participant) may replace the file content; deletion (`DELETE /document/{id}` and cascading deletes from `DELETE /project/{id}`) is **owner-role only**.
- If an upload's S3 write fails mid-batch, already-uploaded S3 objects for that batch are cleaned up and the DB transaction is rolled back - no orphaned S3 objects or "ghost" DB rows are left behind on failure.

---

## AWS Setup

### S3 Bucket
1. Create a bucket (e.g. `project-dashboard-documents`)
2. Block all public access - access is only ever granted via short-lived presigned URLs
3. Region must match the Lambda's region

### Lambda Function
1. Runtime: Python 3.12+
2. Handler: `lambda_s3_handler.handler`
3. Code: `lambda/s3_handler.py` (deploy as a standalone package - it only depends on `boto3`, which is provided by the Lambda runtime)
4. Environment variables:
   - `S3_BUCKET_NAME` - bucket name
   - `PROJECT_STORAGE_LIMIT_BYTES` - default `524288000` (500 MB); should match the API's value
5. IAM role permissions:
   ```json
   {
     "Effect": "Allow",
     "Action": ["s3:ListBucket", "s3:GetObject", "s3:DeleteObject"],
     "Resource": [
       "arn:aws:s3:::YOUR_BUCKET_NAME",
       "arn:aws:s3:::YOUR_BUCKET_NAME/*"
     ]
   }
   ```
   Note the `s3:DeleteObject` permission - the Lambda actively removes files that push a project over quota, not just logs a warning.
6. Trigger: S3 → `ObjectCreated` → prefix `projects/`

### File key format
```
projects/{project_id}/documents/{document_id}_{upload_id}_{filename}
```
The Lambda parses `project_id` from this key via a regex (`^projects/(?P<project_id>\d+)/documents/`) to scope its per-project size calculation.

### Production config via SSM (optional)
For EC2-style deployments, `config.py` supports loading settings from **AWS SSM Parameter Store** instead of a local `.env` file:
- Set `USE_SSM=true` and `SSM_PATH` (default `/project-dashboard/prod/`)
- On startup, all parameters recursively under that path are fetched (with decryption for `SecureString`) and used as config overrides
- If SSM is unreachable, the app logs a warning and falls back to `.env` rather than crashing - useful for local dev where `USE_SSM` should stay `false`

---

## Frontend

A minimal vanilla-JS single-page app is served by FastAPI itself (`StaticFiles` mounted at `/`, after the API routers so it doesn't shadow them). No build step or framework - one `app.js`, hash-based routing (`#/login`, `#/dashboard`, `#/project/{id}`).

- **Session**: JWT is stored in `localStorage` and decoded client-side (base64url) purely to read `sub` (user id) for role-based UI - the server is always the actual source of truth for authorization.
- **Views**: login/register (tabbed form), dashboard (project grid with owner/participant badges, create-project form), project detail (editable info, document list with upload/download/delete, invite form shown only to owners).
- **Downloads**: the app requests `GET /document/{id}`; if the response is JSON it opens the presigned S3 URL directly in a new tab, otherwise it falls back to blob-downloading raw bytes.
- **Error handling**: a central `apiFetch` wrapper normalizes network errors, maps `401` to an automatic logout + redirect to login, and turns Pydantic `422` validation errors into readable per-field messages.

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth` | ❌ | Register user |
| `POST` | `/login` | ❌ | Login, returns JWT |
| `POST` | `/projects` | ✅ | Create project (creator becomes owner) |
| `GET` | `/projects` | ✅ | List accessible projects (owner + participant), with documents |
| `GET` | `/project/{id}/info` | ✅ | Get project details |
| `PUT` | `/project/{id}/info` | ✅ any member | Update project details |
| `DELETE` | `/project/{id}` | ✅ owner role | Delete project + its documents (DB and S3) |
| `GET` | `/project/{id}/documents` | ✅ any member | List completed (non-pending) documents |
| `POST` | `/project/{id}/documents` | ✅ any member | Upload one or more documents (quota-checked) |
| `GET` | `/document/{id}` | ✅ any member | Get a presigned download URL |
| `PUT` | `/document/{id}` | ✅ any member | Replace document content (quota re-checked) |
| `DELETE` | `/document/{id}` | ✅ owner role | Delete document (DB and S3) |
| `POST` | `/project/{id}/invite?user=<login>` | ✅ owner role | Grant participant access by login |
| `GET` | `/project/{id}/share?with=<email>` | ✅ owner role | Generate a signed, time-limited join link (see caveat below) |

---

## Key Design Decisions

1. **S3 keys over full URLs** - storing S3 keys instead of full URLs keeps data portable across regions and bucket renames. Presigned URLs are generated on demand with a 15-minute expiry.

2. **`is_pending` flag** - documents are written to the DB before the S3 upload completes, and only flipped to non-pending after a successful upload/commit. Downloads and listings explicitly filter out pending documents so a half-uploaded file never leaks into a response; failures roll back the DB and clean up any partial S3 writes.

3. **Two-layer quota enforcement, not "Lambda as passive auditor"** - the API enforces the quota synchronously (hard `413` before upload) using a DB-cached size total, guarded by a `SELECT ... FOR UPDATE` lock to prevent concurrent-request races. The Lambda independently recomputes the real total from S3 after the fact and **deletes the offending object** if it still finds an overage - it's a correctness backstop against drift, not just a log line.

4. **`FOR UPDATE` locks** - a project-row lock during uploads (serializes concurrent quota checks for the same project) and a document-row lock during update/delete (serializes concurrent modifications to the same document).

5. **Argon2 password hashing** - chosen over bcrypt alone for stronger resistance to GPU-based attacks; bcrypt is kept registered as a fallback verifier via `pwdlib`.

6. **Authorization centralized in the service layer, with a single ownership source** - every project/document service method funnels through a single `_resolve_access` resolver, and `Project` itself carries no `owner_id` shortcut column - `access.role` is the only place ownership lives, so there's no second field that could ever fall out of sync with it.

7. **SSM-backed config for production** - rather than baking secrets into the image or requiring a mounted `.env` on EC2, `config.py` can pull all settings from AWS SSM Parameter Store at startup, falling back silently to `.env` if SSM isn't reachable (keeps local dev friction-free).

---

## CI Pipeline

Three sequential jobs on every push/PR to `main` (`.github/workflows/ci-cd.yml`):

1. **Lint** - `ruff check` and `ruff format --check` against `src` and `tests`
2. **Test** *(depends on Lint)* - `pytest` with coverage, against a real `postgres:16` service container (not SQLite/mocks), coverage report uploaded as a build artifact
3. **Build & push** *(depends on Test)* - Docker image built with Buildx (with GHA layer caching); **pushed to GHCR only on a push to `main`** - PRs still build the image (to catch Dockerfile breakage) but don't push, keeping CD explicit and separate from CI

---

## Running Tests

```bash
# locally
pytest

# with coverage
pytest --cov=src/app tests/ --cov-report=term-missing

# via docker
docker-compose run app pytest
```

Test infrastructure (`conftest.py`):
- Each test runs against a real Postgres connection wrapped in a transaction that's rolled back afterward - no shared/mutated state between tests, no SQLite substitution.
- S3 is fully mocked (`mock_s3` fixture patches `S3Service.upload_file` / `delete_file` / `generate_download_url`) so tests don't hit real AWS.
- Fixtures provide pre-authenticated headers for three distinct users (`owner_headers`, `participant_headers`, `other_headers`) to drive access-control assertions.

`test_projects.py` covers the full CRUD + access-control matrix for projects and invites: creation validation (missing/short/empty name → `422`), visibility (owner sees own, participant sees invited, stranger sees neither), update permissions (both roles can update), delete permissions (owner-only, participant → `403`), and invite flow (success, self-invite/duplicate/nonexistent-user/participant-inviting all return the correct error codes), plus `401` on every endpoint when unauthenticated.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | ✅ (Docker) | - | Used by docker-compose to provision the Postgres container |
| `DATABASE_URL` | ✅ | - | PostgreSQL async DSN (must match `DB_*` above) |
| `SECRET_KEY` | ✅ | - | JWT signing key (also used to sign share-link tokens) |
| `ALGORITHM` | ❌ | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | - | JWT lifetime |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | ❌ | `None` | AWS credentials (required for document upload/download) |
| `S3_BUCKET_NAME` | ❌ | `None` | S3 bucket name |
| `AWS_REGION` | ❌ | `us-east-1` | AWS region |
| `PROJECT_STORAGE_LIMIT_BYTES` | ❌ | `524288000` | Per-project quota in bytes (500 MB) |
| `USE_SSM` | ❌ | `false` | If `true`, loads config from AWS SSM Parameter Store instead of `.env` |
| `SSM_PATH` | ❌ | `/project-dashboard/prod/` | SSM parameter path prefix (recursive) |

---

## Known Gaps / TODO

- **`/project/{id}/share`** generates and returns a valid HMAC-SHA256-signed join token with a 24-hour expiry, but a corresponding **`GET /join`** endpoint to redeem that token (as described in the original requirements) was not found among the reviewed routes - confirm whether it exists elsewhere or still needs to be built before claiming this optional feature as complete for grading.
- Email delivery for the share link (e.g. via AWS SES) is not implemented - the endpoint currently just returns the `join_url` in the JSON response rather than sending it.
- `dependencies.py` defines a standalone `require_owner()` helper that doesn't appear to be called anywhere - authorization is instead fully handled inside `ProjectService._resolve_access`; worth removing the dead code or wiring it in for clarity.
- **Ownership has no DB-level foreign key back to `users` anymore** - `projects` dropped its `owner_id` column, so ownership now lives only in `access` rows, and the project→access/documents cascade is an ORM-level `cascade="all, delete-orphan"`, not a Postgres `ON DELETE CASCADE`. That only fires through this ORM session; it wouldn't protect against orphaned `access`/`documents` rows from a raw-SQL delete or a different code path. Also open: `Access.user_id` still has a plain FK to `users.id` with no `ondelete` behavior defined, so what happens when a user who owns a project is deleted isn't resolved yet - worth deciding and documenting.