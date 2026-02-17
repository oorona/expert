"""Create a default Oracle Database expert."""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from db.session import async_session
from models.database import Expert, Prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Creating default Oracle Database Expert...")

    async with async_session() as db:
        # Check if expert already exists
        result = await db.execute(
            select(Expert).where(Expert.name == "Oracle Database Expert")
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"Expert already exists with ID {existing.id}")
            return

        # Create the expert
        expert = Expert(
            name="Oracle Database Expert",
            description="Expert in Oracle Database diagnostics, troubleshooting, and optimization. Specializes in analyzing errors, performance issues, and providing actionable solutions.",
            is_active=True
        )

        db.add(expert)
        await db.commit()
        await db.refresh(expert)

        # Link the template prompts to this expert
        result = await db.execute(
            select(Prompt).where(Prompt.name.in_([
                "Template - System (grounded)",
                "Template - User (grounded)"
            ]))
        )
        template_prompts = result.scalars().all()

        for prompt in template_prompts:
            prompt.expert_id = expert.id

        await db.commit()

        logger.info(f"✅ Created Oracle Database Expert with ID {expert.id}")
        logger.info(f"   Linked {len(template_prompts)} template prompts")


if __name__ == "__main__":
    asyncio.run(main())
