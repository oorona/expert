#!/bin/bash
# Complete backup script - backs up database and copies to host for git commit

set -e

echo "================================"
echo "COMPLETE BACKUP PROCEDURE"
echo "================================"

# Step 1: Run backup in container
echo ""
echo "📦 Step 1: Creating backup in container..."
docker exec expert-backend python scripts/backup_all.py

# Step 2: Copy backups to host
echo ""
echo "📂 Step 2: Copying backups to host..."
docker cp expert-backend:/app/backups backend/
docker cp expert-backend:/app/prompts/exports backend/prompts/
docker cp expert-backend:/app/schemas/definitions backend/schemas/

# Step 3: Show what was backed up
echo ""
echo "================================"
echo "✅ BACKUP COMPLETE"
echo "================================"
echo ""
echo "Backed up to:"
echo "  - backend/backups/"
echo "  - backend/prompts/exports/"
echo "  - backend/schemas/definitions/"
echo ""
echo "Next steps:"
echo "  1. git add backend/backups backend/prompts backend/schemas"
echo "  2. git commit -m \"Database backup $(date +%Y-%m-%d)\""
echo "  3. git push"
echo ""
