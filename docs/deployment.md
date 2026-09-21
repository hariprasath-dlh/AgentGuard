# Deployment Runbook

This document is a manual runbook for deploying AgentGuard to a production-like environment using free-tier managed services. It is written for a human who will execute these steps manually — not for automated CI/CD.

> **Actual deployment status:** At the time this documentation was written, AgentGuard has been validated locally with a full test suite (177 Playwright tests across 3 browsers, passing). The system has not been deployed to a live production environment. This runbook describes what a production deployment would look like.

---

## Recommended Free-Tier Services

| Component | Service | Free Tier |
|-----------|---------|-----------|
| Backend API | [Fly.io](https://fly.io) or [Koyeb](https://www.koyeb.com) | Free hobby plan |
| PostgreSQL | [Neon](https://neon.tech) or [Supabase](https://supabase.com) | Free tier with 0.5GB |
| Redis | [Upstash](https://upstash.com) | Free tier (10,000 commands/day) |
| Frontend | [Vercel](https://vercel.com) | Free hobby plan |

---

## Pre-Deployment Checklist

Work through this before starting deployment:

- [ ] Generate a cryptographically random `JWT_SECRET` (minimum 32 bytes)
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- [ ] Provision PostgreSQL database (Neon or Supabase) — note the connection string
- [ ] Provision Redis (Upstash) — note the connection string
- [ ] Have the frontend repository ready with the backend URL known
- [ ] Confirm `CORS_ORIGINS` will match the frontend deployment URL exactly

---

## Step 1: Set Up the Database

### Using Neon

1. Go to [console.neon.tech](https://console.neon.tech), create a project
2. Create a database called `agentguard`
3. Copy the connection string in this format:
   ```
   postgresql://neondb_owner:<password>@<host>.neon.tech/agentguard?sslmode=require
   ```

### Apply Alembic Migrations

The backend uses Alembic for database migrations. From the `backend/` directory:

```bash
cd backend
pip install -r requirements.txt

# Point at the production database
export DATABASE_URL="postgresql://neondb_owner:<password>@<host>.neon.tech/agentguard?sslmode=require"

# Apply all migrations
alembic upgrade head
```

If there are no Alembic migration files (the project used `Base.metadata.create_all()` for development), run this one-time command:

```bash
python -c "
from app.core.config import settings
from app.core.database import Base, engine
from app.models import *
Base.metadata.create_all(bind=engine)
print('Tables created.')
"
```

Verify tables were created by connecting to the database and listing tables.

---

## Step 2: Set Up Redis

### Using Upstash

1. Go to [console.upstash.com](https://console.upstash.com), create a Redis database
2. Choose a region close to your backend deployment
3. Copy the Redis URL in this format:
   ```
   rediss://:password@<host>.upstash.io:6379
   ```

> **Note:** Upstash free tier enforces a daily command limit. For heavy testing, monitor usage.

---

## Step 3: Deploy the Backend

### Using Fly.io

Install the Fly CLI and authenticate:

```bash
# Install Fly CLI (follow https://fly.io/docs/getting-started/installing-flyctl/)
flyctl auth login
```

Initialize the Fly app from the `backend/` directory:

```bash
cd backend
flyctl launch --name agentguard-api --no-deploy
```

This creates a `fly.toml`. Edit it to ensure:

```toml
[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
```

Set the required secrets (environment variables):

```bash
flyctl secrets set \
  DATABASE_URL="postgresql://..." \
  REDIS_URL="rediss://..." \
  JWT_SECRET="<your-32-byte-secret>" \
  API_BASE_URL="https://agentguard-api.fly.dev" \
  CORS_ORIGINS="https://your-frontend.vercel.app" \
  AGENTGUARD_ENV="production"
```

Deploy:

```bash
flyctl deploy
```

Verify the deployment:

```bash
curl https://agentguard-api.fly.dev/health
# Expected: {"status": "healthy"}

curl https://agentguard-api.fly.dev/ready
# Expected: {"status": "ready"}
```

---

## Step 4: Deploy the Frontend

### Using Vercel

1. Push the repository to GitHub
2. Go to [vercel.com](https://vercel.com) and import the repository
3. Set the **Root Directory** to `frontend`
4. Set the **Framework Preset** to `Vite` (TanStack Start is Vite-based)
5. Set environment variables in Vercel project settings:

   | Variable | Value |
   |----------|-------|
   | `VITE_API_BASE_URL` | `https://agentguard-api.fly.dev/api/v1` |

6. Deploy

After deployment, copy the Vercel deployment URL (e.g., `https://agentguard.vercel.app`).

---

## Step 5: Update CORS Configuration

Go back to the backend and update the CORS origin to match the actual Vercel URL:

```bash
flyctl secrets set CORS_ORIGINS="https://agentguard.vercel.app"
flyctl deploy
```

Test that the frontend can reach the backend:
1. Open the Vercel URL in a browser
2. Attempt to register or log in
3. Verify the browser's Network tab shows 200 responses from the backend API

---

## Step 6: Create Initial Admin User

Register the first admin user via the API:

```bash
curl -X POST https://agentguard-api.fly.dev/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@yourorg.com",
    "password": "SecureP@ss123",
    "full_name": "System Admin",
    "organization_name": "Your Organization",
    "organization_slug": "your-org"
  }'
```

> **Note:** The first user registered in a new organization is automatically assigned the ADMIN role.

---

## Environment Variables Reference

All environment variables the backend reads:

| Variable | Required | Default (dev) | Production Value |
|----------|----------|---------------|-----------------|
| `DATABASE_URL` | Yes | SQLite fallback | PostgreSQL connection string |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Upstash Redis URL |
| `JWT_SECRET` | Yes | Hardcoded dev value | Random 32+ byte hex string |
| `API_BASE_URL` | No | `http://localhost:8000` | `https://agentguard-api.fly.dev` |
| `CORS_ORIGINS` | Yes | `http://localhost:3000` | Frontend deployment URL |
| `AGENTGUARD_ENV` | No | `development` | `production` |

> **Security:** The default `JWT_SECRET` in `config.py` is `"changeme_secret_key_jwt_dev_only_32b!"`. This must be overridden in production. Any token signed with the default secret is exploitable if the default is publicly known.

---

## Rollback Procedure

### Backend (Fly.io)

Fly.io retains recent deployment releases. To roll back to the previous version:

```bash
flyctl releases list
flyctl deploy --image <previous-image-digest>
```

Or force a specific release:

```bash
flyctl releases rollback <release-number>
```

### Frontend (Vercel)

Vercel maintains deployment history. In the Vercel dashboard:
1. Go to Deployments
2. Find the previous successful deployment
3. Click "Promote to Production"

### Database

There is no automated database rollback. If a migration causes data problems:
1. Connect directly to the database
2. Manually reverse any schema changes
3. Restore from a Neon/Supabase backup if data is corrupted

**Recovery objectives:**
- RPO (Recovery Point Objective): < 1 hour — Neon provides point-in-time restore to any point in the last 7 days on the free tier
- RTO (Recovery Time Objective): < 4 hours — redeploy backend from existing Docker image + restore database

---

## Production Checklist

Run through this after every production deployment:

- [ ] `GET /health` returns `{"status": "healthy"}`
- [ ] `GET /ready` returns `{"status": "ready"}`
- [ ] `POST /api/v1/auth/login` with a test user succeeds and returns a token
- [ ] Frontend loads and displays the login screen
- [ ] Frontend can authenticate and reach the dashboard
- [ ] `CORS_ORIGINS` set to exact frontend URL (no trailing slash)
- [ ] `JWT_SECRET` is not the default dev value
- [ ] `DATABASE_URL` points to PostgreSQL (not SQLite)
- [ ] `REDIS_URL` is reachable from backend (test with a guard/check call)
- [ ] HTTPS is enforced (Fly.io `force_https = true`)

---

## Running Locally with Docker Compose

For local development, the included `docker-compose.yml` starts PostgreSQL and Redis:

```bash
# Start infrastructure only
docker compose up -d postgres redis

# Run backend locally (connects to containerized PG + Redis)
cd backend
uvicorn app.main:app --reload --port 8000

# Run frontend locally
cd frontend
npm run dev
```

The full `docker compose up` also starts the backend and a frontend placeholder, but the frontend Dockerfile entry in `docker-compose.yml` is a placeholder (`tail -f /dev/null`) that doesn't actually run the frontend development server. Run the frontend with `npm run dev` directly.

---

## Known Deployment Gaps

These items are not yet fully automated:

1. **No CI/CD pipeline** — deployments are manual. A GitHub Actions workflow that builds, tests, and deploys on push to `main` does not exist yet.
2. **No health-check-based rollback** — if the backend starts but fails the health check, Fly.io will attempt a rollback, but this is not configured explicitly.
3. **No secrets rotation policy** — there is no procedure for rotating the `JWT_SECRET` or API keys without invalidating all existing sessions.
4. **No database migration safety gate** — Alembic `upgrade head` is run manually. There is no automated check that the migration is backward-compatible before deploying.
5. **No alerting** — there is no uptime monitoring, error rate alerting, or on-call notification configuration.
