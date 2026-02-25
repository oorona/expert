import json
import os

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Category, OutputSchema, Prompt, Schema, SchemaCategory

# Canonical locations — single source of truth on disk
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts", "templates")
SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), "schemas", "definitions")

_PROMPT_TEMPLATES = [
    ("Template - System (grounded)",    "system", "grounded",    "grounded_system.txt"),
    ("Template - User (grounded)",      "user",   "grounded",    "grounded_user.txt"),
    ("Template - System (file_search)", "system", "file_search", "file_search_system.txt"),
    ("Template - User (file_search)",   "user",   "file_search", "file_search_user.txt"),
]


async def seed_defaults(session: AsyncSession):
    """Insert default prompts, categories and schemas only on first run.
    DB is source of truth after initial seeding — all edits go through the admin UI."""
    await _seed_categories(session)
    await session.flush()  # categories must exist before SchemaCategory FK references them
    await _seed_prompt_templates(session)
    await _seed_output_schema(session)
    await _seed_category_schemas(session)
    await session.flush()


async def reload_defaults(session: AsyncSession):
    """Force-reload prompts, categories and schemas from disk, overwriting DB values.
    Called from the admin UI 'Reload Defaults' action."""
    await _reload_categories(session)
    await session.flush()  # categories must be committed before SchemaCategory FK references them
    await _reload_prompt_templates(session)
    await _reload_category_schemas(session)
    await session.flush()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


async def _seed_categories(session: AsyncSession):
    """Seed categories from categories_manifest.json if the table is empty."""
    result = await session.execute(select(Category).limit(1))
    if result.scalar_one_or_none():
        return  # Already seeded

    manifest_path = os.path.join(SCHEMAS_DIR, "categories_manifest.json")
    if not os.path.exists(manifest_path):
        return

    with open(manifest_path, "r") as f:
        categories = json.load(f)

    for cat in categories:
        session.add(Category(
            name=cat["name"],
            display_name=cat["display_name"],
            description=cat.get("description", ""),
            intent_description=cat.get("intent_description", ""),
            example_inputs=cat.get("example_inputs", []),
            key_outputs=cat.get("key_outputs", []),
        ))


async def _reload_categories(session: AsyncSession):
    """Reload categories from manifest, updating existing and adding missing ones."""
    manifest_path = os.path.join(SCHEMAS_DIR, "categories_manifest.json")
    if not os.path.exists(manifest_path):
        return

    with open(manifest_path, "r") as f:
        categories = json.load(f)

    for cat in categories:
        result = await session.execute(
            select(Category).where(Category.name == cat["name"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.display_name = cat["display_name"]
            existing.description = cat.get("description", existing.description)
            existing.intent_description = cat.get("intent_description", existing.intent_description)
            existing.example_inputs = cat.get("example_inputs", existing.example_inputs)
            existing.key_outputs = cat.get("key_outputs", existing.key_outputs)
        else:
            session.add(Category(
                name=cat["name"],
                display_name=cat["display_name"],
                description=cat.get("description", ""),
                intent_description=cat.get("intent_description", ""),
                example_inputs=cat.get("example_inputs", []),
                key_outputs=cat.get("key_outputs", []),
            ))


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------


async def _seed_prompt_templates(session: AsyncSession):
    """Insert default prompts only if missing."""
    for tpl_name, ptype, pcat, filename in _PROMPT_TEMPLATES:
        filepath = os.path.join(PROMPTS_DIR, filename)
        if not os.path.exists(filepath):
            continue
        result = await session.execute(
            select(Prompt).where(Prompt.name == tpl_name)
        )
        if not result.scalar_one_or_none():
            with open(filepath, "r") as f:
                content = f.read()
            session.add(Prompt(
                name=tpl_name,
                prompt_type=ptype,
                prompt_category=pcat,
                content=content,
            ))


async def _reload_prompt_templates(session: AsyncSession):
    """Overwrite prompt content from disk files (UI-triggered reset)."""
    for tpl_name, ptype, pcat, filename in _PROMPT_TEMPLATES:
        filepath = os.path.join(PROMPTS_DIR, filename)
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r") as f:
            content = f.read()
        result = await session.execute(
            select(Prompt).where(Prompt.name == tpl_name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.content = content
        else:
            session.add(Prompt(
                name=tpl_name,
                prompt_type=ptype,
                prompt_category=pcat,
                content=content,
            ))


# ---------------------------------------------------------------------------
# Legacy OutputSchema (fallback used by diagnose router)
# ---------------------------------------------------------------------------


async def _seed_output_schema(session: AsyncSession):
    schema_path = os.path.join(SCHEMAS_DIR, "diagnostic_output.json")
    if not os.path.exists(schema_path):
        return
    result = await session.execute(
        select(OutputSchema).where(OutputSchema.name == "default_diagnostic")
    )
    if not result.scalar_one_or_none():
        with open(schema_path, "r") as f:
            schema = json.load(f)
        session.add(OutputSchema(name="default_diagnostic", schema_json=schema))


# ---------------------------------------------------------------------------
# Category-based Schemas (seeded from schemas_manifest.json)
# ---------------------------------------------------------------------------


async def _seed_category_schemas(session: AsyncSession):
    """Seed the Schema + SchemaCategory tables from schemas_manifest.json if empty."""
    result = await session.execute(select(Schema).limit(1))
    if result.scalar_one_or_none():
        return  # Already seeded — don't overwrite

    manifest_path = os.path.join(SCHEMAS_DIR, "schemas_manifest.json")
    if not os.path.exists(manifest_path):
        return

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    for entry in manifest:
        schema = Schema(
            name=entry["name"],
            description=entry.get("description", ""),
            json_schema=entry["json_schema"],
            is_active=entry.get("is_active", True),
        )
        session.add(schema)
        await session.flush()

        for cat_mapping in entry.get("categories", []):
            session.add(SchemaCategory(
                schema_id=schema.id,
                category_name=cat_mapping["category_name"],
                priority=cat_mapping.get("priority", 1),
            ))


async def _reload_category_schemas(session: AsyncSession):
    """Reload schemas from manifest: update json_schema and rebuild all category mappings."""
    manifest_path = os.path.join(SCHEMAS_DIR, "schemas_manifest.json")
    if not os.path.exists(manifest_path):
        return

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    for entry in manifest:
        result = await session.execute(
            select(Schema).where(Schema.name == entry["name"])
        )
        schema = result.scalar_one_or_none()
        if schema:
            schema.json_schema = entry["json_schema"]
            schema.description = entry.get("description", schema.description)
            schema.is_active = entry.get("is_active", schema.is_active)

            # Rebuild category mappings from manifest
            await session.execute(
                delete(SchemaCategory).where(SchemaCategory.schema_id == schema.id)
            )
            for cat_mapping in entry.get("categories", []):
                session.add(SchemaCategory(
                    schema_id=schema.id,
                    category_name=cat_mapping["category_name"],
                    priority=cat_mapping.get("priority", 1),
                ))
        else:
            schema = Schema(
                name=entry["name"],
                description=entry.get("description", ""),
                json_schema=entry["json_schema"],
                is_active=entry.get("is_active", True),
            )
            session.add(schema)
            await session.flush()

            for cat_mapping in entry.get("categories", []):
                session.add(SchemaCategory(
                    schema_id=schema.id,
                    category_name=cat_mapping["category_name"],
                    priority=cat_mapping.get("priority", 1),
                ))
