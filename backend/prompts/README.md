# Prompts Backup and Recovery System

This directory contains prompt templates and backup/restore scripts to prevent data loss.

## Directory Structure

```
prompts/
├── templates/          # Template prompts for default experts
│   ├── grounded_system.txt
│   ├── grounded_user.txt
│   └── file_search_*.txt
├── exports/           # Full database exports (auto-generated)
│   ├── prompts_manifest.json
│   └── *.txt files
├── classification_prompt.py
└── README.md
```

## Template Prompts

Template prompts in `templates/` are the source of truth for:
- **Grounded prompts**: Used for diagnostic mode with structured JSON output
- **File search prompts**: Used for RAG mode with knowledge base files

These are version-controlled and should be edited directly when you need to update default prompts.

## Backup System

### Export Current Prompts from Database

```bash
# From backend container
python scripts/export_prompts.py
```

This creates:
- `exports/prompts_manifest.json` - Full metadata for all prompts
- `exports/*.txt` - Individual prompt content files
- Updates `templates/` with latest template prompts

**Run this regularly or before any database operations!**

### Restore Prompts to Database

```bash
# From backend container
python scripts/import_prompts.py
```

This restores prompts from the manifest file. Use this to:
- Recover after database deletion
- Restore to a previous version
- Sync prompts across environments

### Creating Template Prompts for New Experts

```bash
# From backend container
python scripts/create_template_prompts.py
```

## Recovery Workflow

If the database is deleted or corrupted:

1. **Rebuild database schema**:
   ```bash
   alembic upgrade head
   ```

2. **Seed categories and schemas**:
   ```bash
   python scripts/seed_simple.py
   python scripts/update_schemas_json.py
   ```

3. **Restore prompts from backup**:
   ```bash
   python scripts/import_prompts.py
   ```

4. **Create default experts**:
   ```bash
   python scripts/seed_default_expert.py
   ```

5. **Verify restoration**:
   ```bash
   python -c "
   import asyncio
   from sqlalchemy import select
   from db.session import async_session
   from models.database import Prompt, Expert

   async def check():
       async with async_session() as db:
           prompts = await db.execute(select(Prompt))
           experts = await db.execute(select(Expert))
           print(f'Prompts: {len(prompts.scalars().all())}')
           print(f'Experts: {len(experts.scalars().all())}')

   asyncio.run(check())
   "
   ```

## Best Practices

1. **Export before risky operations**: Always run `export_prompts.py` before database migrations, schema changes, or deletions
2. **Commit exports to git**: The `exports/` directory should be committed so prompts are version-controlled
3. **Edit templates directly**: Update template files, then run import to sync to database
4. **Regular backups**: Set up a cron job or CI task to export prompts daily

## Gitignore Note

The `exports/` directory should **NOT** be in `.gitignore` - we want these backed up in version control.
