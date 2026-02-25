"""Export all schemas from database to files for backup and version control."""
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


async def main():
    logger.info("Exporting all schemas from database to files...")

    # Ensure directory exists
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)

    async with async_session() as db:
        result = await db.execute(select(Schema).order_by(Schema.id))
        schemas = result.scalars().all()

        if not schemas:
            logger.warning("No schemas found in database")
            return

        # Export all schemas as JSON manifest
        manifest = []

        for schema in schemas:
            schema_data = {
                "id": schema.id,
                "name": schema.name,
                "description": schema.description,
                "json_schema": schema.json_schema,
                "is_active": schema.is_active,
            }
            manifest.append(schema_data)

            # Save individual schema to file
            filename = f"{schema.name.lower()}.json"
            filepath = SCHEMAS_DIR / filename

            # Write pretty-printed JSON
            filepath.write_text(json.dumps(schema.json_schema, indent=2))
            logger.info(f"  ✓ Exported {schema.name} → {filename}")

        # Save manifest
        manifest_path = SCHEMAS_DIR / "schemas_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        logger.info(f"\n✅ Exported {len(schemas)} schemas")
        logger.info(f"   Files: {SCHEMAS_DIR}")
        logger.info(f"   Manifest: {manifest_path}")


if __name__ == "__main__":
    asyncio.run(main())
