#!/usr/bin/env python3
"""
One-time script to update existing prompts and schema with infographic generation support.
Run this with: python update_prompts_and_schema.py
"""
import asyncio
import json
import os
from pathlib import Path

from sqlalchemy import select, update
from db.session import async_session
from models.database import OutputSchema, Prompt


INFOGRAPHIC_SECTION = """
## Infographic Suggestion

After analyzing the error, determine if a visual diagram/infographic would help illustrate:
- System architecture or data flow
- Error propagation through components
- Before/after comparison of configurations
- Complex troubleshooting decision trees
- Memory/resource allocation patterns

If a visual would be helpful, set `visual_aid_suggested` to `true` and provide a detailed `image_generation_prompt` that:
- Describes the type of diagram (architecture diagram, flowchart, comparison chart, etc.)
- Specifies all components, connections, and labels clearly
- Uses descriptive visual language (colors, shapes, arrows, layout)
- Focuses on clarity and educational value
- Is suitable for generating a technical infographic

The prompt should be comprehensive enough (200-400 words) for an AI image generator to create a useful, accurate technical diagram.

Example: "Create a technical architecture diagram showing a three-tier web application. At the top, show a blue rectangular box labeled 'Load Balancer (nginx)' with incoming HTTPS traffic arrows. Below that, show three green boxes in a row labeled 'App Server 1', 'App Server 2', 'App Server 3', connected by bidirectional arrows to the load balancer. Below the app servers, show a red cylinder labeled 'Database (PostgreSQL)' with connection arrows from each app server. Highlight the connection between App Server 2 and the database with a red X mark and error symbol, indicating a connection timeout. Add text annotations explaining the error flow."
"""


async def update_schema():
    """Update the output schema to include infographic fields."""
    print("Updating output schema...")

    # Load the updated schema from file
    schema_path = Path(__file__).parent / "data" / "schemas" / "diagnostic_output.json"
    with open(schema_path, "r") as f:
        new_schema = json.load(f)

    async with async_session() as session:
        # Find the default diagnostic schema
        result = await session.execute(
            select(OutputSchema).where(OutputSchema.name == "default_diagnostic")
        )
        schema_obj = result.scalar_one_or_none()

        if schema_obj:
            schema_obj.schema_json = new_schema
            await session.commit()
            print("✓ Schema updated successfully")
        else:
            print("✗ Schema 'default_diagnostic' not found")


async def update_prompts():
    """Update all system prompts to include infographic guidance."""
    print("\nUpdating system prompts...")

    async with async_session() as session:
        # Find all system prompts (both grounded and file_search)
        result = await session.execute(
            select(Prompt).where(
                Prompt.prompt_type == "system",
                Prompt.prompt_category.in_(["grounded", "file_search"])
            )
        )
        prompts = result.scalars().all()

        if not prompts:
            print("✗ No system prompts found")
            return

        for prompt in prompts:
            # Check if infographic section already exists
            if "Infographic Suggestion" in prompt.content:
                print(f"  ⊙ '{prompt.name}' already has infographic section, skipping")
                continue

            # Add the infographic section at the end
            prompt.content = prompt.content.rstrip() + "\n" + INFOGRAPHIC_SECTION
            print(f"  ✓ Updated '{prompt.name}'")

        await session.commit()
        print(f"\n✓ Updated {len([p for p in prompts if 'Infographic Suggestion' not in p.content])} prompts")


async def main():
    print("=" * 60)
    print("Updating Database for Infographic Generation Support")
    print("=" * 60)

    await update_schema()
    await update_prompts()

    print("\n" + "=" * 60)
    print("Update complete! Restart your backend for changes to take effect.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
