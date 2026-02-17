# Disaster Recovery Guide

**IMPORTANT**: This guide exists because we lost all data when the database was deleted without backups. Never let this happen again.

## Quick Recovery (After Database Deletion)

If the database is deleted or corrupted, follow these steps in order:

### 1. Rebuild Database Schema

```bash
cd /home/iktdts/apps/website/expert/backend
docker exec expert-backend alembic upgrade head
```

### 2. Restore from Latest Backup

```bash
# This restores EVERYTHING: schemas, categories, prompts, experts
docker exec expert-backend python scripts/restore_all.py
```

### 3. Verify Restoration

```bash
docker exec expert-backend python -c "
import asyncio
from sqlalchemy import select, func
from db.session import async_session
from models.database import Schema, Category, Prompt, Expert

async def verify():
    async with async_session() as db:
        schemas = await db.execute(select(func.count(Schema.id)))
        categories = await db.execute(select(func.count(Category.name)))
        prompts = await db.execute(select(func.count(Prompt.id)))
        experts = await db.execute(select(func.count(Expert.id)))

        print('📊 Restored Database:')
        print(f'   Schemas: {schemas.scalar()}')
        print(f'   Categories: {categories.scalar()}')
        print(f'   Prompts: {prompts.scalar()}')
        print(f'   Experts: {experts.scalar()}')

asyncio.run(verify())
"
```

Expected output:
- Schemas: 5
- Categories: 20
- Prompts: 8+
- Experts: 2+

## Regular Backups (CRITICAL - Do This Regularly!)

### Create Complete Backup

**Run this BEFORE any risky database operations!**

```bash
docker exec expert-backend python scripts/backup_all.py
```

This creates a timestamped backup in `/app/backups/YYYYMMDD_HHMMSS/` containing:
- `schemas.json` - All 5 JSON schemas (Fixer, Analyst, Guide, Inspector, Teacher)
- `categories.json` - All 20 categories
- `prompts.json` - All system/user prompts for all experts
- `experts.json` - All expert definitions
- `summary.json` - Backup metadata

### Copy Backup to Host (For Git Commit)

```bash
docker cp expert-backend:/app/backups /home/iktdts/apps/website/expert/backend/
cd /home/iktdts/apps/website/expert
git add backend/backups
git commit -m "Database backup $(date +%Y-%m-%d)"
git push
```

### Automated Backup (Recommended)

Add to crontab to run daily at 2 AM:

```bash
crontab -e
```

Add line:
```
0 2 * * * docker exec expert-backend python scripts/backup_all.py && docker cp expert-backend:/app/backups /home/iktdts/apps/website/expert/backend/backups
```

## Individual Component Backups

### Export Prompts Only

```bash
docker exec expert-backend python scripts/export_prompts.py
docker cp expert-backend:/app/prompts/exports /home/iktdts/apps/website/expert/backend/prompts/
```

Creates:
- `prompts/exports/prompts_manifest.json` - All prompt metadata
- `prompts/exports/*.txt` - Individual prompt content files
- `prompts/templates/*.txt` - Template prompts (grounded, file_search)

### Export Schemas Only

```bash
docker exec expert-backend python scripts/export_schemas.py
docker cp expert-backend:/app/schemas/definitions /home/iktdts/apps/website/expert/backend/schemas/
```

Creates:
- `schemas/definitions/fixer.json`
- `schemas/definitions/analyst.json`
- `schemas/definitions/guide.json`
- `schemas/definitions/inspector.json`
- `schemas/definitions/teacher.json`
- `schemas/definitions/schemas_manifest.json`

## Template Prompt Sources

The following template prompts are version-controlled as the source of truth:

### Grounded Prompts (Diagnostic Mode)
- **System**: `backend/prompts/templates/grounded_system.txt`
- **User**: `backend/prompts/templates/grounded_user.txt`

### File Search Prompts (RAG Mode)
- **System**: `backend/prompts/templates/file_search_system.txt`
- **User**: `backend/prompts/templates/file_search_user.txt`

**To update template prompts**:
1. Edit the `.txt` files directly
2. Run `import_prompts.py` to sync to database
3. Commit changes to git

## Backup Locations

All backups should exist in THREE places:

1. **Container**: `/app/backups/` (temporary, lost if container recreated)
2. **Host**: `/home/iktdts/apps/website/expert/backend/backups/` (survives container recreation)
3. **Git repository**: Committed and pushed (survives host failure)

## What NOT to Do (Lessons Learned)

❌ **DO NOT** drop/delete the database without a recent backup
❌ **DO NOT** run `TRUNCATE`, `DROP TABLE`, or `DROP DATABASE` in production
❌ **DO NOT** assume data only in the database is safe
❌ **DO NOT** skip backups before migrations or schema changes

## Recovery from Specific Scenarios

### Scenario: Missing Prompts for Expert

```bash
# 1. Check what prompts exist
docker exec expert-backend python -c "
import asyncio
from sqlalchemy import select
from db.session import async_session
from models.database import Prompt

async def check():
    async with async_session() as db:
        result = await db.execute(select(Prompt.id, Prompt.name, Prompt.prompt_category, Prompt.expert_id))
        for row in result.all():
            print(f'ID {row[0]}: {row[1]} ({row[2]}) - Expert {row[3]}')

asyncio.run(check())
"

# 2. Restore from backup
docker exec expert-backend python scripts/import_prompts.py
```

### Scenario: Missing or Corrupted Schemas

```bash
# Restore schemas from version-controlled definitions
docker exec expert-backend python scripts/import_schemas.py
```

### Scenario: TOAST Corruption (Like We Had)

```bash
# DO NOT try to repair - just restore from backup
# 1. Create new database
docker exec expert-postgres psql -U postgres -c "DROP DATABASE expert;"
docker exec expert-postgres psql -U postgres -c "CREATE DATABASE expert OWNER postgres;"

# 2. Rebuild schema
docker exec expert-backend alembic upgrade head

# 3. Restore all data
docker exec expert-backend python scripts/restore_all.py
```

## Testing Backups

**Test your backups regularly!** A backup you haven't tested is not a backup.

```bash
# 1. Create test backup
docker exec expert-backend python scripts/backup_all.py

# 2. Note the timestamp from output
# 3. In a test environment, restore it
docker exec expert-backend python scripts/restore_all.py 20260217_030231

# 4. Verify the data
```

## Contact

If you lose data and this guide doesn't help, check:
- Git history: `git log --all -- backend/backups/`
- Docker volumes: `docker volume ls`
- Container logs: `docker logs expert-backend`

**Remember**: The database is NOT the source of truth. Version-controlled files are.
