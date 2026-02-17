"""Restore complete database from backup files."""
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete
from db.session import async_session
from models.database import Prompt, Schema, Category, Expert, SchemaCategory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKUP_DIR = Path(__file__).parent.parent / "backups"


async def main(backup_name: str = None):
    logger.info("=" * 60)
    logger.info("COMPLETE DATABASE RESTORE")
    logger.info("=" * 60)

    # Find backup directory
    if backup_name:
        backup_path = BACKUP_DIR / backup_name
    else:
        # Use latest backup
        backups = sorted(BACKUP_DIR.glob("*"), reverse=True)
        if not backups:
            logger.error("No backups found!")
            return
        backup_path = backups[0]

    if not backup_path.exists():
        logger.error(f"Backup not found: {backup_path}")
        return

    logger.info(f"📁 Restoring from: {backup_path}")

    # Load backup files
    schemas_file = backup_path / "schemas.json"
    categories_file = backup_path / "categories.json"
    schema_categories_file = backup_path / "schema_categories.json"
    prompts_file = backup_path / "prompts.json"
    experts_file = backup_path / "experts.json"

    if not all([schemas_file.exists(), categories_file.exists(), prompts_file.exists()]):
        logger.error("Incomplete backup - missing required files")
        return

    schemas_data = json.loads(schemas_file.read_text())
    categories_data = json.loads(categories_file.read_text())
    schema_categories_data = json.loads(schema_categories_file.read_text()) if schema_categories_file.exists() else []
    prompts_data = json.loads(prompts_file.read_text())
    experts_data = json.loads(experts_file.read_text()) if experts_file.exists() else []

    logger.info(f"\n📊 Backup contains:")
    logger.info(f"   Schemas: {len(schemas_data)}")
    logger.info(f"   Schema-Category mappings: {len(schema_categories_data)}")
    logger.info(f"   Categories: {len(categories_data)}")
    logger.info(f"   Prompts: {len(prompts_data)}")
    logger.info(f"   Experts: {len(experts_data)}")

    async with async_session() as db:
        # Restore categories first (no dependencies)
        logger.info("\n📂 Restoring categories...")
        for cat_data in categories_data:
            result = await db.execute(
                select(Category).where(Category.name == cat_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.display_name = cat_data["display_name"]
                existing.description = cat_data["description"]
                existing.intent_description = cat_data["intent_description"]
                existing.example_inputs = cat_data["example_inputs"]
                existing.key_outputs = cat_data["key_outputs"]
                logger.info(f"   ↻ Updated: {cat_data['name']}")
            else:
                category = Category(**cat_data)
                db.add(category)
                logger.info(f"   + Created: {cat_data['name']}")

        await db.commit()

        # Restore schemas
        logger.info("\n📋 Restoring schemas...")
        for schema_data in schemas_data:
            result = await db.execute(
                select(Schema).where(Schema.name == schema_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.description = schema_data["description"]
                existing.json_schema = schema_data["json_schema"]
                existing.is_active = schema_data["is_active"]
                logger.info(f"   ↻ Updated: {schema_data['name']}")
            else:
                # Don't use ID from backup - let DB assign new one
                schema = Schema(
                    name=schema_data["name"],
                    description=schema_data["description"],
                    json_schema=schema_data["json_schema"],
                    is_active=schema_data["is_active"],
                )
                db.add(schema)
                logger.info(f"   + Created: {schema_data['name']}")

        await db.commit()

        # Restore schema-category mappings
        if schema_categories_data:
            logger.info("\n🔗 Restoring schema-category mappings...")
            for mapping in schema_categories_data:
                if not mapping.get("schema_name"):
                    continue
                schema_res = await db.execute(
                    select(Schema).where(Schema.name == mapping["schema_name"])
                )
                schema = schema_res.scalar_one_or_none()
                if not schema:
                    logger.warning(f"   ⚠ Schema '{mapping['schema_name']}' not found, skipping")
                    continue
                existing = await db.execute(
                    select(SchemaCategory).where(
                        SchemaCategory.schema_id == schema.id,
                        SchemaCategory.category_name == mapping["category_name"],
                    )
                )
                if not existing.scalar_one_or_none():
                    db.add(SchemaCategory(
                        schema_id=schema.id,
                        category_name=mapping["category_name"],
                        priority=mapping.get("priority", 1),
                    ))
                    logger.info(f"   + {mapping['schema_name']} → {mapping['category_name']}")
            await db.commit()

        # Restore experts (if any)
        if experts_data:
            logger.info("\n👤 Restoring experts...")
            for expert_data in experts_data:
                result = await db.execute(
                    select(Expert).where(Expert.name == expert_data["name"])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.description = expert_data["description"]
                    existing.is_active = expert_data["is_active"]
                    logger.info(f"   ↻ Updated: {expert_data['name']}")
                else:
                    expert = Expert(
                        name=expert_data["name"],
                        description=expert_data["description"],
                        is_active=expert_data["is_active"],
                    )
                    db.add(expert)
                    logger.info(f"   + Created: {expert_data['name']}")

            await db.commit()

        # Restore prompts
        logger.info("\n💬 Restoring prompts...")
        for prompt_data in prompts_data:
            result = await db.execute(
                select(Prompt).where(Prompt.name == prompt_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.content = prompt_data["content"]
                existing.prompt_type = prompt_data["prompt_type"]
                existing.prompt_category = prompt_data["prompt_category"]
                existing.is_active = prompt_data["is_active"]
                # Update expert_id only if it exists in backup
                if prompt_data.get("expert_id"):
                    existing.expert_id = prompt_data["expert_id"]
                logger.info(f"   ↻ Updated: {prompt_data['name']}")
            else:
                prompt = Prompt(
                    name=prompt_data["name"],
                    prompt_type=prompt_data["prompt_type"],
                    prompt_category=prompt_data["prompt_category"],
                    content=prompt_data["content"],
                    expert_id=prompt_data.get("expert_id"),
                    is_active=prompt_data["is_active"],
                )
                db.add(prompt)
                logger.info(f"   + Created: {prompt_data['name']}")

        await db.commit()

        logger.info("\n" + "=" * 60)
        logger.info("✅ RESTORE COMPLETE")
        logger.info("=" * 60)


if __name__ == "__main__":
    import sys

    backup_name = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(backup_name))
