

# Project Dashboard — README
(1st draft from Claude, needs revision)
---

## Table of Contents
1. [Overview](#overview)
2. [Setup & Run Locally](#setup--run-locally)
3. [Architecture Overview](#architecture-overview)
4. [Data Model](#data-model)
5. [Auth & Authorization Flow](#auth--authorization-flow)
6. [AWS Setup](#aws-setup)
7. [API Reference](#api-reference)
8. [Key Design Decisions](#key-design-decisions)
9. [CI Pipeline](#ci-pipeline)
10. [Running Tests](#running-tests)

---

## Overview

A backend service for managing projects and their documents. Users can create projects, upload documents (PDF/DOCX), and share projects with other users. Files are stored in AWS S3. An AWS Lambda function monitors storage usage per project.

**Stack:**
- Python 3.12+, FastAPI
- PostgreSQL + SQLAlchemy (async)
- Docker + docker-compose
- AWS S3 (file storage) + AWS Lambda (S3 event processing)
- GitHub Actions (CI)

---

## Setup & Run Locally

### Prerequisites
- Docker + docker-compose
- AWS account with S3 bucket and credentials

### 1. Clone the repository
```bash
git clone https://github.com/your-username/project-dashboard.git
cd project-dashboard
```

### 2. Create `.env` file
```bash
cp .env.example .env
```

Fill in the values:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/dashboard
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
S3_BUCKET_NAME=your-bucket-name
AWS_REGION=us-east-1
PROJECT_STORAGE_LIMIT_BYTES=524288000
```

### 3. Run with Docker
```bash
docker-compose up --build
```

App will be available at `http://localhost:8000`

### 4. API Docs
```
http://localhost:8000/docs      # Swagger UI
http://localhost:8000/redoc     # ReDoc
```

---

## Architecture Overview

```
Client
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
          AWS Lambda (s3_handler.py)
                │
                └── sums project file sizes
                    logs warning if quota exceeded
```

**Request flow:**
1. Client sends JWT-authenticated request
2. FastAPI validates token, resolves role (owner/participant)
3. Service layer executes business logic
4. Files are streamed directly to S3 (never stored on server)
5. On upload, S3 triggers Lambda which recalculates project storage usage

---

## Data Model

```
users
├── id          PK
├── login       unique
└── hashed_password

projects
├── id          PK
├── name
├── description
└── owner_id    FK → users.id

documents
├── id          PK
├── name
├── url         S3 key
├── size        bytes
├── is_pending  upload state flag
├── project_id  FK → projects.id
└── owner_id    FK → users.id

access
├── id          PK
├── project_id  FK → projects.id
├── user_id     FK → users.id
└── role        owner | participant
```

### Normalization rationale
- **`access` table** is a normalized join table for project membership. This avoids storing role arrays on the `projects` table (1NF/2NF compliance) and makes permission queries efficient with indexed lookups.
- **`documents.url`** stores the S3 key (not a full URL) — presigned URLs are generated on demand, keeping stored data stable and bucket-location-agnostic.
- **`documents.is_pending`** is a state flag that prevents incomplete uploads from being visible to users — a denormalization trade-off that avoids a separate `uploads` table and keeps queries simple.
- **`documents.size`** is stored in the DB to avoid S3 API calls for quota checks on every upload — a deliberate denormalization for performance. Lambda recalculates from S3 as the source of truth.

### ORM vs raw SQL
SQLAlchemy async ORM is used throughout. A raw SQL equivalent of the access check would be:
```sql
SELECT role FROM access
WHERE project_id = $1 AND user_id = $2;
```
ORM advantage: type safety, relationship loading, migration integration.
Raw SQL advantage: simpler debugging, no N+1 risk, predictable query shape.

---

## Auth & Authorization Flow

### JWT Issuance (`POST /login`)
1. User submits `login` + `password`
2. Password verified against `argon2` hash
3. JWT issued with `user_id` in payload, expires in 1 hour
4. All subsequent requests require `Authorization: Bearer <token>`

### Role enforcement
Two roles exist:

| Role | Permissions |
|------|-------------|
| `owner` | Full access — create, read, update, delete, invite |
| `participant` | Read + update only — cannot delete project or documents |

- Owner is determined by `projects.owner_id`
- Participants are stored in the `access` table
- Every protected endpoint resolves the caller's role before executing

### Access check flow
```
Request → extract JWT → get user_id
  → check projects.owner_id == user_id → "owner"
  → else check access table → "participant"
  → else → 403 Forbidden
```

---

## AWS Setup

### S3 Bucket
1. Create bucket (e.g., `project-dashboard-documents`)
2. Block all public access ✅
3. Region must match Lambda region

### Lambda Function
1. Runtime: Python 3.12
2. Handler: `s3_handler.handler`
3. Code: paste contents of `lambda/s3_handler.py`
4. Environment variables:
   - `S3_BUCKET_NAME` — your bucket name
   - `PROJECT_STORAGE_LIMIT_BYTES` — default `524288000` (500MB)
5. IAM role permissions:
   ```json
   {
     "Effect": "Allow",
     "Action": ["s3:ListBucket", "s3:GetObject"],
     "Resource": [
       "arn:aws:s3:::YOUR_BUCKET_NAME",
       "arn:aws:s3:::YOUR_BUCKET_NAME/*"
     ]
   }
   ```
6. Trigger: S3 → `ObjectCreated` → prefix `projects/`

### File key format
```
projects/{project_id}/documents/{document_id}_{upload_id}_{filename}
```
Lambda parses `project_id` from this key to scope the storage calculation.

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth` | ❌ | Register user |
| `POST` | `/login` | ❌ | Login, returns JWT |
| `POST` | `/projects` | ✅ | Create project |
| `GET` | `/projects` | ✅ | List accessible projects |
| `GET` | `/project/{id}/info` | ✅ | Get project details |
| `PUT` | `/project/{id}/info` | ✅ | Update project details |
| `DELETE` | `/project/{id}` | ✅ owner only | Delete project + documents |
| `GET` | `/project/{id}/documents` | ✅ | List documents |
| `POST` | `/project/{id}/documents` | ✅ | Upload documents |
| `GET` | `/document/{id}` | ✅ | Get presigned download URL |
| `PUT` | `/document/{id}` | ✅ | Replace document |
| `DELETE` | `/document/{id}` | ✅ owner only | Delete document |
| `POST` | `/project/{id}/invite` | ✅ owner only | Invite user by login |

---

## Key Design Decisions

1. **S3 keys over full URLs** — storing S3 keys instead of full URLs keeps data portable across regions and bucket renames. Presigned URLs are generated on demand with a 15-minute expiry.

2. **`is_pending` flag** — documents are written to DB before S3 upload completes. The flag prevents half-uploaded files from leaking into responses. On failure, the record is rolled back.

3. **Lambda as observer, not enforcer** — the FastAPI service enforces the quota hard block synchronously before upload. Lambda recalculates from S3 post-upload as an independent audit/log layer. This avoids Lambda being a synchronous dependency in the upload path.

4. **`FOR UPDATE` lock on project** — concurrent uploads to the same project acquire a row-level lock on the `projects` table to serialize quota checks and prevent race conditions.

5. **Argon2 password hashing** — chosen over bcrypt for stronger resistance to GPU-based attacks. `pwdlib` is used as the hashing interface.

6. **`NullPool` not used** — the app runs in Docker (persistent process), not Lambda, so SQLAlchemy's default connection pool is appropriate.

---

## CI Pipeline

On every push/PR:
1. **Lint** — `ruff`
2. **Test** — `pytest`
3. **Build** — Docker image
4. **Push** — to container registry

See `.github/workflows/ci-cd.yml` for full configuration.

---

## Running Tests

```bash
# locally
pytest

# with coverage
pytest --cov=app tests/

# via docker
docker-compose run app pytest
```

Tests cover:
- Auth (register, login, JWT validation)
- Authorization (owner vs participant enforcement)
- Project CRUD
- Document upload, download, delete
- Access control edge cases

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | PostgreSQL async DSN |
| `SECRET_KEY` | ✅ | — | JWT signing key |
| `ALGORITHM` | ❌ | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | — | JWT lifetime |
| `AWS_ACCESS_KEY_ID` | ✅ | — | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | ✅ | — | AWS credentials |
| `S3_BUCKET_NAME` | ✅ | — | S3 bucket name |
| `AWS_REGION` | ❌ | `us-east-1` | AWS region |
| `PROJECT_STORAGE_LIMIT_BYTES` | ❌ | `524288000` | Per-project quota (500MB) |