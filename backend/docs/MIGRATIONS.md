# Database Migrations

## Overview

Migrations run as **ECS Fargate tasks** using a dedicated migration Docker image.

---

## How It Works

```
1. Developer creates migration → alembic/versions/abc123_add_column.py
2. Push to main → GitHub Actions builds migration image
3. Image pushed to → migrations-{env}-ecr
4. Manually trigger → database-migrations.yml workflow
5. ECS task runs → alembic upgrade head
6. Migration complete ✅
```

---

## Files

| File | Purpose |
|------|---------|
| `docker/Dockerfile.migrations` | Migration container (Alembic + models) |
| `.github/workflows/build-migration-image.yml` | Builds migration image on changes |
| `.github/workflows/database-migrations.yml` | Runs migration via ECS task |
| `infrastructure` repo | Terraform (ECS cluster, task def) |

---

## Running Migrations

### 1. Create Migration (Dev)

```bash
# Make model change
vim app/database/models/database.py

# Generate migration
poetry run alembic revision --autogenerate -m "add email column"

# Test locally
docker-compose exec backend alembic upgrade head

# Commit
git add alembic/versions/*.py app/database/models/
git commit -m "Add email column migration"
git push
```

### 2. Build Migration Image (Automatic)

When you push changes to `alembic/**` or `app/database/models/**`:
- GitHub Actions → `build-migration-image.yml` triggers
- Builds → `docker/Dockerfile.migrations`
- Pushes to → `migrations-production-ecr:latest`

### 3. Run Migration (Manual)

```
GitHub Actions → Run workflow
  ↓
Select: "Database Migrations (ECS)"
  ↓
Choose: staging or production
  ↓
Click: "Run workflow"
  ↓
Result: Migration runs in ECS, logs in CloudWatch
```

---

## Terraform Setup

Already configured in `infrastructure/modules/migrations/`:

- **ECS Cluster**: `migrations-{env}-cluster`
- **ECS Service**: `migrations-{env}-service` (desired_count=0)
- **Task Command**: `alembic upgrade head`
- **Image Source**: `migrations-{env}-ecr:latest`

**Update needed**: Change task command to use Alembic properly (see below).

---

## Troubleshooting

**Issue**: Migration task fails to start
- **Fix**: Check ECS task definition exists: `aws ecs describe-task-definition --task-definition migrations-production-task`

**Issue**: Can't connect to database
- **Fix**: Verify security groups allow migration task → RDS on port 5432

**Issue**: Migration image not found
- **Fix**: Manually trigger `build-migration-image.yml` workflow

---