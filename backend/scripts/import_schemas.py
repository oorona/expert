"""Import schemas from backup files to database."""
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from db.session import async_session
from models.database import Schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCHEMAS_DIR = Path(__file__).parent.parent / "db" / "schemas" / "definitions"
MANIFEST_FILE = SCHEMAS_DIR / "schemas_manifest.json"


async def main():
    logger.info("Importing schemas from backup files to database...")

    if not MANIFEST_FILE.exists():
        logger.error(f"Manifest file not found: {MANIFEST_FILE}")
        logger.error("Run export_schemas.py first to create a backup")
        return

    # Load manifest
    manifest = json.loads(MANIFEST_FILE.read_text())
    logger.info(f"Found {len(manifest)} schemas in manifest")

    async with async_session() as db:
        imported = 0
        updated = 0

        for schema_data in manifest:
            # Check if schema already exists by name
            result = await db.execute(
                select(Schema).where(Schema.name == schema_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing schema
                existing.description = schema_data.get("description", "")
                existing.json_schema = schema_data["json_schema"]
                existing.is_active = schema_data["is_active"]
                logger.info(f"  ↻ Updated: {schema_data['name']}")
                updated += 1
            else:
                # Create new schema
                schema = Schema(
                    name=schema_data["name"],
                    description=schema_data.get("description", ""),
                    json_schema=schema_data["json_schema"],
                    is_active=schema_data["is_active"],
                )
                db.add(schema)
                logger.info(f"  + Created: {schema_data['name']}")
                imported += 1

        await db.commit()

        logger.info(f"\n✅ Import completed!")
        logger.info(f"   Created: {imported}")
        logger.info(f"   Updated: {updated}")


if __name__ == "__main__":
    asyncio.run(main())
