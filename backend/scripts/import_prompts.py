"""Import prompts from backup files to database."""
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from db.session import async_session
from models.database import Prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EXPORT_DIR = Path(__file__).parent.parent / "prompts" / "exports"
MANIFEST_FILE = EXPORT_DIR / "prompts_manifest.json"


async def main():
    logger.info("Importing prompts from backup files to database...")

    if not MANIFEST_FILE.exists():
        logger.error(f"Manifest file not found: {MANIFEST_FILE}")
        logger.error("Run export_prompts.py first to create a backup")
        return

    # Load manifest
    manifest = json.loads(MANIFEST_FILE.read_text())
    logger.info(f"Found {len(manifest)} prompts in manifest")

    async with async_session() as db:
        imported = 0
        skipped = 0
        updated = 0

        for prompt_data in manifest:
            # Check if prompt already exists by name
            result = await db.execute(
                select(Prompt).where(Prompt.name == prompt_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing prompt
                existing.content = prompt_data["content"]
                existing.prompt_type = prompt_data["prompt_type"]
                existing.prompt_category = prompt_data["prompt_category"]
                existing.is_active = prompt_data["is_active"]
                # Don't update expert_id to preserve current associations
                logger.info(f"  ↻ Updated: {prompt_data['name']}")
                updated += 1
            else:
                # Create new prompt (without expert_id, will be assigned later)
                prompt = Prompt(
                    name=prompt_data["name"],
                    prompt_type=prompt_data["prompt_type"],
                    prompt_category=prompt_data["prompt_category"],
                    content=prompt_data["content"],
                    is_active=prompt_data["is_active"],
                )
                db.add(prompt)
                logger.info(f"  + Created: {prompt_data['name']}")
                imported += 1

        await db.commit()

        logger.info(f"\n✅ Import completed!")
        logger.info(f"   Created: {imported}")
        logger.info(f"   Updated: {updated}")
        logger.info(f"   Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
