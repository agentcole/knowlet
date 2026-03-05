# Knowlet

Knowlet is a multi-tenant knowledge platform for teams to upload documents and meetings, curate wiki pages, and chat with AI over indexed company knowledge.

## Highlights

- Multi-tenant workspaces with role-based access (`owner`, `admin`, `member`)
- Document ingestion and chunked vector indexing
- Meeting transcription pipeline and wiki publishing flow
- Wiki with folders, drag-and-drop organization, manual ordering, and revisions
- Admin-only wiki page deletion
- Admin-only wiki reindex trigger from the UI
- RAG chat over indexed documents and wiki content
- User default language preference used across assistant workflows

## Tech Stack

- Frontend: React + Vite + TypeScript + React Query + Tailwind
- Backend: FastAPI + SQLAlchemy (async) + Alembic
- Workers: Celery + Redis
- Database: PostgreSQL
- AI/ML: Anthropic (LLM responses/workflows)
- AI/ML: Voyage AI (embeddings)
- AI/ML: Deepgram (meeting transcription)

## Quick Start (Docker)

### 1) Configure environment

```bash
cp .env.example .env
```

Update `.env` with real API keys:

- `ANTHROPIC_API_KEY`
- `VOYAGE_API_KEY`
- `DEEPGRAM_API_KEY`

Optional email notifications (SMTP):

- `EMAIL_NOTIFICATIONS_ENABLED=true`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME` (default `Knowlet`)
- `SMTP_USE_TLS` / `SMTP_USE_SSL`
- `APP_BASE_URL` (used in email links/messages)

### 2) Start the stack

```bash
docker compose up --build -d
```

### 3) Open the apps

- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API docs: [http://localhost:8001/docs](http://localhost:8001/docs)
- Health check: [http://localhost:8001/api/health](http://localhost:8001/api/health)

## Common Commands

Start services:

```bash
docker compose up -d
```

Stop services:

```bash
docker compose down
```

Follow logs:

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f celery-worker
```

Rebuild after dependency or Dockerfile changes:

```bash
docker compose build
docker compose up -d
```

## Wiki Reindex

Admins can reindex all wiki/document vectors from the Wiki page using the **Reindex Wiki** button.

Use this when:

- Search/chat results feel stale
- You changed wiki structure/content in bulk
- You migrated data and need a clean vector rebuild

The action is queued asynchronously and processed by the Celery worker.

## Email Notifications

Knowlet supports SMTP email notifications for tenant membership events:

- User invited to tenant
- User role changed
- User removed from tenant

If SMTP is not configured or disabled, app behavior continues without failing the request.

## Local Troubleshooting

Port already in use (`5432`):

- This project maps Postgres to host `5433` by default.
- If needed, change `POSTGRES_PORT` in `.env`.

Containers not running:

```bash
docker compose ps
docker compose up -d
```

Worker tasks not picked up:

```bash
docker compose up -d --force-recreate celery-worker
```

## Project Layout

```text
.
├── backend/          # FastAPI app, models, routers, workers, migrations
├── frontend/         # React/Vite UI
├── docker-compose.yml
└── .env.example
```

## Notes

- This repository is currently set up for local/dev usage first.
- For production, add hardened secrets management, TLS, and deployment-specific configuration.
