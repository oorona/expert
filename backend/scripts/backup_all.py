"""Complete backup of all database content to files."""
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from db.session import async_session
from models.database import Prompt, Schema, Category, Expert, SchemaCategory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKUP_DIR = Path(__file__).parent.parent / "backups"


async def main():
    logger.info("=" * 60)
    logger.info("COMPLETE DATABASE BACKUP")
    logger.info("=" * 60)

    # Create backup directory with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / timestamp
    backup_path.mkdir(parents=True, exist_ok=True)

    async with async_session() as db:
        # Backup schemas
        logger.info("\n📋 Backing up schemas...")
        result = await db.execute(select(Schema).order_by(Schema.id))
        schemas = result.scalars().all()
        schemas_data = [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "json_schema": s.json_schema,
                "is_active": s.is_active,
            }
            for s in schemas
        ]
        (backup_path / "schemas.json").write_text(json.dumps(schemas_data, indent=2))
        logger.info(f"   ✓ {len(schemas)} schemas")

        # Backup schema-category mappings
        logger.info("\n🔗 Backing up schema-category mappings...")
        result = await db.execute(
            select(SchemaCategory).order_by(SchemaCategory.schema_id, SchemaCategory.category_name)
        )
        mappings = result.scalars().all()
        mappings_data = [
            {
                "schema_name": next((s["name"] for s in schemas_data if s["id"] == m.schema_id), None),
                "category_name": m.category_name,
                "priority": m.priority,
            }
            for m in mappings
        ]
        (backup_path / "schema_categories.json").write_text(json.dumps(mappings_data, indent=2))
        logger.info(f"   ✓ {len(mappings)} mappings")

        # Backup categories
        logger.info("\n📂 Backing up categories...")
        result = await db.execute(select(Category).order_by(Category.name))
        categories = result.scalars().all()
        categories_data = [
            {
                "name": c.name,
                "display_name": c.display_name,
                "description": c.description,
                "intent_description": c.intent_description,
                "example_inputs": c.example_inputs,
                "key_outputs": c.key_outputs,
            }
            for c in categories
        ]
        (backup_path / "categories.json").write_text(
            json.dumps(categories_data, indent=2)
        )
        logger.info(f"   ✓ {len(categories)} categories")

        # Backup prompts
        logger.info("\n💬 Backing up prompts...")
        result = await db.execute(select(Prompt).order_by(Prompt.id))
        prompts = result.scalars().all()
        prompts_data = [
            {
                "id": p.id,
                "name": p.name,
                "prompt_type": p.prompt_type,
                "prompt_category": p.prompt_category,
                "content": p.content,
                "expert_id": p.expert_id,
                "is_active": p.is_active,
            }
            for p in prompts
        ]
        (backup_path / "prompts.json").write_text(json.dumps(prompts_data, indent=2))
        logger.info(f"   ✓ {len(prompts)} prompts")

        # Backup experts
        logger.info("\n👤 Backing up experts...")
        result = await db.execute(select(Expert).order_by(Expert.id))
        experts = result.scalars().all()
        experts_data = [
            {
                "id": e.id,
                "name": e.name,
                "description": e.description,
                "is_active": e.is_active,
            }
            for e in experts
        ]
        (backup_path / "experts.json").write_text(json.dumps(experts_data, indent=2))
        logger.info(f"   ✓ {len(experts)} experts")

        # Create backup summary
        summary = {
            "timestamp": timestamp,
            "counts": {
                "schemas": len(schemas),
                "schema_categories": len(mappings),
                "categories": len(categories),
                "prompts": len(prompts),
                "experts": len(experts),
            },
        }
        (backup_path / "summary.json").write_text(json.dumps(summary, indent=2))

        logger.info("\n" + "=" * 60)
        logger.info(f"✅ BACKUP COMPLETE: {backup_path}")
        logger.info("=" * 60)
        logger.info(f"   Schemas: {len(schemas)}")
        logger.info(f"   Schema-Category mappings: {len(mappings)}")
        logger.info(f"   Categories: {len(categories)}")
        logger.info(f"   Prompts: {len(prompts)}")
        logger.info(f"   Experts: {len(experts)}")
        logger.info(f"\n📁 Backup location: {backup_path}")


if __name__ == "__main__":
    asyncio.run(main())
