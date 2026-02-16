# Fixing PostgreSQL Database Corruption

## Error

```
asyncpg.exceptions.DataCorruptedError: missing chunk number 0 for toast value 17664 in pg_toast_16755
```

This indicates **PostgreSQL TOAST data corruption**. TOAST (The Oversized-Attribute Storage Technique) is PostgreSQL's mechanism for storing large field values (text, JSON, etc.) in a separate table.

## Immediate Workaround

The application now has error handling to skip the re-embedding step during startup, so it will continue to run despite the corruption. However, you should still fix the database corruption.

## Fix Options

### Option 1: REINDEX and VACUUM (Recommended First Step)

This attempts to rebuild the corrupted indexes and clean up the database without losing data.

```bash
# 1. Connect to the database
docker exec -it expert-db psql -U postgres -d expert

# 2. Inside psql, run these commands:
REINDEX TABLE incidents;
VACUUM FULL incidents;

# 3. If that works, also reindex other tables for good measure:
REINDEX TABLE prompts;
REINDEX TABLE output_schemas;
REINDEX TABLE experts;

# 4. Exit psql
\q

# 5. Restart the backend to retry re-embedding
docker restart expert-backend

# 6. Check logs
docker logs -f expert-backend
```

### Option 2: pg_dump and Restore (If Option 1 Fails)

If REINDEX/VACUUM doesn't fix the corruption, you can rebuild the database from a dump. This usually fixes TOAST corruption because pg_dump reads the logical data and writes it fresh.

```bash
# 1. Backup the current database
docker exec expert-db pg_dump -U postgres expert > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Check the backup succeeded
ls -lh backup_*.sql

# 3. Drop and recreate the database
docker exec -it expert-db psql -U postgres -c "DROP DATABASE expert;"
docker exec -it expert-db psql -U postgres -c "CREATE DATABASE expert;"

# 4. Restore from backup
cat backup_*.sql | docker exec -i expert-db psql -U postgres expert

# 5. Restart backend
docker restart expert-backend

# 6. Check logs
docker logs -f expert-backend
```

### Option 3: Fresh Database (Nuclear Option)

If you don't need the existing data, start fresh:

```bash
# 1. Stop all containers
docker compose down

# 2. Remove the database volume (⚠️ DELETES ALL DATA)
docker volume ls | grep postgres
docker volume rm expert_postgres-data
# or whatever the volume name is

# 3. Start fresh
docker compose up -d

# 4. Check logs
docker logs -f expert-backend
```

### Option 4: Skip Corrupted Records (Advanced)

If only specific incidents are corrupted and you want to keep the rest:

```sql
-- Connect to database
docker exec -it expert-db psql -U postgres -d expert

-- Find and delete corrupted incidents
-- This will attempt to read each incident and fail on corrupted ones
SELECT id FROM incidents WHERE error_text IS NOT NULL LIMIT 1000;

-- If you identify corrupted IDs, delete them:
DELETE FROM incidents WHERE id IN (123, 456, 789);

-- Then REINDEX and VACUUM
REINDEX TABLE incidents;
VACUUM FULL incidents;

\q
```

## Preventing Future Corruption

### Check Disk Space

Database corruption often happens when disk space runs out:

```bash
# Check disk space
df -h

# Check Docker volumes
docker system df -v
```

### Check Docker Volume Health

```bash
# Inspect the database volume
docker volume inspect expert_postgres-data

# Check container logs for disk errors
docker logs expert-db | grep -i "error\|corrupt\|disk"
```

### Enable WAL Archiving (Production)

For production systems, enable PostgreSQL WAL archiving for better recovery:

```yaml
# In docker-compose.yml, add to postgres service:
environment:
  - POSTGRES_INITDB_ARGS=--data-checksums
command: postgres -c wal_level=replica -c archive_mode=on
```

### Regular Backups

Set up automated backups:

```bash
# Add to crontab (daily backup at 2 AM)
0 2 * * * docker exec expert-db pg_dump -U postgres expert | gzip > /backup/expert_$(date +\%Y\%m\%d).sql.gz

# Keep only last 7 days
find /backup -name "expert_*.sql.gz" -mtime +7 -delete
```

## Verification

After fixing, verify the database is healthy:

```sql
-- Connect to database
docker exec -it expert-db psql -U postgres -d expert

-- Check for corrupted data
SELECT COUNT(*) FROM incidents WHERE error_text IS NOT NULL;

-- Check TOAST tables
SELECT relname, n_tup_ins, n_tup_upd, n_tup_del
FROM pg_stat_user_tables
WHERE relname LIKE 'pg_toast%';

-- Check database size
SELECT pg_size_pretty(pg_database_size('expert'));

\q
```

## Application Behavior After Fix

After fixing the database corruption and restarting:

1. **Re-embedding will complete**: The `_reembed_incidents()` function will successfully update old embeddings
2. **Logs will show**: "Re-embedding complete" or "All incident embeddings are up-to-date"
3. **Diagnosis will work normally**: New incidents can be created without errors

## Root Causes

Common causes of TOAST corruption:

1. **Disk full**: Most common cause - database runs out of space during write
2. **Unclean shutdown**: Container/system crashed during write operation
3. **Hardware issues**: Failing disk, memory corruption
4. **File system issues**: ext4/xfs errors, mount problems
5. **Docker volume issues**: Corrupted overlay filesystem

## Getting Help

If the corruption persists:

1. Check Docker host system logs: `dmesg | grep -i error`
2. Check PostgreSQL logs: `docker logs expert-db | tail -100`
3. Run PostgreSQL integrity check: `VACUUM FULL ANALYZE;`
4. Consider migrating to a new Docker volume or host

## Summary

**Quick Fix (Application Continues)**:
- ✅ Error handling added - application starts despite corruption
- ⚠️ Re-embedding skipped until database is fixed

**Permanent Fix**:
1. Try REINDEX + VACUUM first
2. If that fails, pg_dump and restore
3. Last resort: fresh database (data loss)

**Prevention**:
- Monitor disk space
- Regular backups
- Enable data checksums
- Avoid hard container kills
