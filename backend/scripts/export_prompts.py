"""Export template prompts from database back to the canonical disk files."""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from db.session import async_session
from models.database import Prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "db" / "prompts" / "templates"

_TEMPLATE_FILENAMES = {
    "Template - System (grounded)":    "grounded_system.txt",
    "Template - User (grounded)":      "grounded_user.txt",
    "Template - System (file_search)": "file_search_system.txt",
    "Template - User (file_search)":   "file_search_user.txt",
}


async def main():
    logger.info("Exporting template prompts from database to %s ...", TEMPLATES_DIR)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    async with async_session() as db:
        result = await db.execute(select(Prompt).order_by(Prompt.id))
        prompts = result.scalars().all()

        if not prompts:
            logger.warning("No prompts found in database")
            return

        exported = 0
        for prompt in prompts:
            filename = _TEMPLATE_FILENAMES.get(prompt.name)
            if not filename:
                continue
            filepath = TEMPLATES_DIR / filename
            filepath.write_text(prompt.content)
            logger.info("  Exported '%s' -> %s", prompt.name, filename)
            exported += 1

        logger.info("Done — %d template file(s) written to %s", exported, TEMPLATES_DIR)


if __name__ == "__main__":
    asyncio.run(main())
