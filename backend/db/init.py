import json
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import OutputSchema, Prompt

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "prompts")
SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "schemas")


async def seed_defaults(session: AsyncSession):
    """Insert default prompts and schemas only on first run (DB is source of truth).
    After initial seeding, all edits go through the admin UI."""

    # --- Seed global prompt templates (only if missing) ---
    templates = [
        ("Template - System (grounded)", "system", "grounded", "system_diagnostic.md"),
        ("Template - User (grounded)", "user", "grounded", "user_template.md"),
        ("Template - System (file_search)", "system", "file_search", "system_file_search.md"),
        ("Template - User (file_search)", "user", "file_search", "user_file_search.md"),
    ]
    for tpl_name, ptype, pcat, filename in templates:
        filepath = os.path.join(PROMPTS_DIR, filename)
        if os.path.exists(filepath):
            result = await session.execute(
                select(Prompt).where(Prompt.name == tpl_name)
            )
            if not result.scalar_one_or_none():
                with open(filepath, "r") as f:
                    content = f.read()
                session.add(
                    Prompt(
                        name=tpl_name,
                        prompt_type=ptype,
                        prompt_category=pcat,
                        content=content,
                    )
                )

    # --- Output schema (only if missing) ---
    schema_path = os.path.join(SCHEMAS_DIR, "diagnostic_output.json")
    if os.path.exists(schema_path):
        result = await session.execute(
            select(OutputSchema).where(OutputSchema.name == "default_diagnostic")
        )
        if not result.scalar_one_or_none():
            with open(schema_path, "r") as f:
                schema = json.load(f)
            session.add(
                OutputSchema(name="default_diagnostic", schema_json=schema)
            )

    await session.flush()
