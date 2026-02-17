"""Create missing template prompts for grounded mode."""
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

GROUNDED_SYSTEM_PROMPT = """You are an expert database administrator and technical troubleshooting specialist.

When a user presents an error or technical issue:
1. Analyze the error message, stack trace, and context carefully
2. Identify the root cause of the problem
3. Provide clear, actionable resolution steps with exact commands
4. Include preventive measures to avoid recurrence
5. Use technical precision while remaining accessible

Always structure your response according to the provided JSON schema.
Be thorough, accurate, and solution-focused."""

GROUNDED_USER_PROMPT = """Please analyze this technical issue and provide a comprehensive diagnostic response:

{{error_text}}

Provide your analysis in the required JSON format with:
- Clear error summary
- Root cause analysis
- Step-by-step resolution with exact commands
- Preventive measures
- Appropriate severity level"""


async def main():
    logger.info("Creating template prompts...")

    async with async_session() as db:
        prompts_to_create = [
            {
                "name": "Template - System (grounded)",
                "prompt_type": "system",
                "prompt_category": "grounded",
                "content": GROUNDED_SYSTEM_PROMPT,
            },
            {
                "name": "Template - User (grounded)",
                "prompt_type": "user",
                "prompt_category": "grounded",
                "content": GROUNDED_USER_PROMPT,
            },
        ]

        for prompt_data in prompts_to_create:
            result = await db.execute(
                select(Prompt).where(Prompt.name == prompt_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(f"  ✓ {prompt_data['name']} already exists")
            else:
                prompt = Prompt(**prompt_data)
                db.add(prompt)
                logger.info(f"  + Created {prompt_data['name']}")

        await db.commit()
        logger.info("✅ Template prompts ready!")


if __name__ == "__main__":
    asyncio.run(main())
