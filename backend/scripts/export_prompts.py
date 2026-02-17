"""Export all prompts from database to files for backup and version control."""
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

TEMPLATES_DIR = Path(__file__).parent.parent / "prompts" / "templates"
EXPORT_DIR = Path(__file__).parent.parent / "prompts" / "exports"


async def main():
    logger.info("Exporting all prompts from database to files...")

    # Ensure directories exist
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_session() as db:
        result = await db.execute(select(Prompt).order_by(Prompt.id))
        prompts = result.scalars().all()

        if not prompts:
            logger.warning("No prompts found in database")
            return

        # Export all prompts as JSON manifest
        manifest = []

        for prompt in prompts:
            prompt_data = {
                "id": prompt.id,
                "name": prompt.name,
                "prompt_type": prompt.prompt_type,
                "prompt_category": prompt.prompt_category,
                "content": prompt.content,
                "expert_id": prompt.expert_id,
                "is_active": prompt.is_active,
            }
            manifest.append(prompt_data)

            # Save individual prompt content to text file
            safe_name = prompt.name.replace(" ", "_").replace("/", "-").replace("(", "").replace(")", "")
            filename = f"{prompt.id}_{safe_name}.txt"
            filepath = EXPORT_DIR / filename

            filepath.write_text(prompt.content)
            logger.info(f"  ✓ Exported {prompt.name} → {filename}")

        # Save manifest
        manifest_path = EXPORT_DIR / "prompts_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info(f"\n✅ Exported {len(prompts)} prompts")
        logger.info(f"   Files: {EXPORT_DIR}")
        logger.info(f"   Manifest: {manifest_path}")

        # Also save template prompts to templates directory
        template_prompts = [p for p in prompts if "Template" in p.name]
        if template_prompts:
            logger.info(f"\n📋 Copying {len(template_prompts)} template prompts to templates/")
            for prompt in template_prompts:
                if "grounded" in prompt.prompt_category:
                    filename = f"grounded_{prompt.prompt_type}.txt"
                elif "file_search" in prompt.prompt_category:
                    filename = f"file_search_{prompt.prompt_type}.txt"
                else:
                    filename = f"{prompt.prompt_category}_{prompt.prompt_type}.txt"

                filepath = TEMPLATES_DIR / filename
                filepath.write_text(prompt.content)
                logger.info(f"  ✓ {filename}")


if __name__ == "__main__":
    asyncio.run(main())
