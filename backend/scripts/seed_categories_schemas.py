"""Seed categories and schemas from spec files."""
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import async_session, engine
from models.database import Base, Category, Schema, SchemaCategory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_categories_file(file_path: Path) -> list[dict]:
    """Parse categories.txt and extract category information."""
    content = file_path.read_text()
    categories = []

    # Split by numbered sections
    sections = re.split(r'\n(\d+)\.\s+(.+?)(?=\n\s+Intent:)', content, re.MULTILINE)

    for i in range(1, len(sections), 3):
        if i + 2 < len(sections):
            # Get category name and normalize it
            display_name = sections[i + 1].strip()
            name = display_name.replace(" / ", "_").replace(" & ", "_").replace(" ", "_")

            # Extract section content
            section_content = sections[i + 2] if i + 2 < len(sections) else ""

            # Parse intent
            intent_match = re.search(r'Intent:\s*(.+?)(?=\n\s+User Input:|$)', section_content, re.DOTALL)
            intent = intent_match.group(1).strip() if intent_match else ""

            # Parse user input examples
            examples = []
            user_input_match = re.search(r'User Input:\s*(.+?)(?=\n\s+Key Output|$)', section_content, re.DOTALL)
            if user_input_match:
                user_input_text = user_input_match.group(1).strip()
                # Extract examples between quotes
                examples = re.findall(r'"([^"]+)"', user_input_text)

            # Parse key outputs
            key_outputs = []
            key_output_match = re.search(r'Key Output Sections?:\s*(.+?)(?=\n\d+\.|$)', section_content, re.DOTALL)
            if key_output_match:
                key_output_text = key_output_match.group(1).strip()
                # Extract items (could be bullets or comma-separated)
                key_outputs = [
                    item.strip().rstrip('.')
                    for item in re.split(r'\n\s*(?:[-•]|\w+:)', key_output_text)
                    if item.strip() and not item.strip().startswith('Sections')
                ]
                # Clean up formatting
                key_outputs = [k for k in key_outputs if k and len(k) > 3]

            categories.append({
                "name": name,
                "display_name": display_name,
                "description": intent,
                "intent_description": intent,
                "example_inputs": examples[:5],  # Limit to 5 examples
                "key_outputs": key_outputs[:10]  # Limit to 10 outputs
            })

    return categories


def parse_schemas_file(file_path: Path) -> tuple[list[dict], dict[str, list[tuple[str, int]]]]:
    """Parse schemas.txt and extract schema definitions and category mappings.

    Returns:
        Tuple of (schemas list, category_mappings dict)
    """
    content = file_path.read_text()
    schemas = []
    category_mappings = {}

    # Split by schema sections
    sections = re.split(r'\n(\d+)\.\s+(?:The\s+)?["""](.+?)["""]?\s+Schema', content)

    for i in range(1, len(sections), 3):
        if i + 2 < len(sections):
            schema_name = sections[i + 1].strip()
            section_content = sections[i + 2]

            # Extract target categories
            categories_match = re.search(r'Target Categories?:\s*(.+?)(?=\n|$)', section_content)
            target_categories = []
            if categories_match:
                cat_text = categories_match.group(1).strip()
                target_categories = [c.strip() for c in cat_text.split(',')]

            # Extract JSON schema
            # Find the JSON object (starts with { and ends with })
            json_match = re.search(r'(\{[\s\S]+?\n\})\s*(?=\n\d+\.|$)', section_content)
            if json_match:
                try:
                    schema_json = json.loads(json_match.group(1))

                    schemas.append({
                        "name": schema_name,
                        "description": f"{schema_name} schema for {', '.join(target_categories)}",
                        "json_schema": schema_json,
                        "is_active": True
                    })

                    # Store category mappings
                    # Performance_Tuning gets different priorities for Fixer vs Inspector
                    mappings = []
                    for cat in target_categories:
                        if cat == "Performance_Tuning":
                            if schema_name == "Fixer":
                                mappings.append((cat, 1))  # Priority 1 (default)
                            elif schema_name == "Inspector":
                                mappings.append((cat, 2))  # Priority 2 (fallback)
                            else:
                                mappings.append((cat, 1))
                        else:
                            mappings.append((cat, 1))

                    category_mappings[schema_name] = mappings

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON for {schema_name}: {e}")

    return schemas, category_mappings


async def seed_categories(db: AsyncSession, categories_data: list[dict]):
    """Insert categories into database."""
    logger.info(f"Seeding {len(categories_data)} categories...")

    for cat_data in categories_data:
        # Check if category already exists
        result = await db.execute(
            select(Category).where(Category.name == cat_data["name"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"  Category {cat_data['name']} already exists, skipping")
        else:
            category = Category(**cat_data)
            db.add(category)
            logger.info(f"  Added category: {cat_data['name']}")

    await db.commit()
    logger.info("Categories seeded successfully")


async def seed_schemas(
    db: AsyncSession,
    schemas_data: list[dict],
    category_mappings: dict[str, list[tuple[str, int]]]
):
    """Insert schemas and their category mappings into database."""
    logger.info(f"Seeding {len(schemas_data)} schemas...")

    for schema_data in schemas_data:
        # Check if schema already exists
        result = await db.execute(
            select(Schema).where(Schema.name == schema_data["name"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"  Schema {schema_data['name']} already exists, skipping")
            schema = existing
        else:
            schema = Schema(**schema_data)
            db.add(schema)
            await db.flush()  # Get the ID
            logger.info(f"  Added schema: {schema_data['name']} (id={schema.id})")

        # Add category associations
        if schema.name in category_mappings:
            for cat_name, priority in category_mappings[schema.name]:
                # Check if mapping already exists
                result = await db.execute(
                    select(SchemaCategory).where(
                        SchemaCategory.schema_id == schema.id,
                        SchemaCategory.category_name == cat_name
                    )
                )
                existing_mapping = result.scalar_one_or_none()

                if not existing_mapping:
                    assoc = SchemaCategory(
                        schema_id=schema.id,
                        category_name=cat_name,
                        priority=priority
                    )
                    db.add(assoc)
                    logger.info(f"    Mapped {cat_name} to {schema.name} (priority={priority})")

    await db.commit()
    logger.info("Schemas seeded successfully")


async def main():
    """Main seeding function."""
    logger.info("Starting database seeding...")

    # Get spec file paths
    specs_dir = Path(__file__).parent.parent / "specs"
    categories_file = specs_dir / "categories.txt"
    schemas_file = specs_dir / "schemas.txt"

    if not categories_file.exists():
        logger.error(f"Categories file not found: {categories_file}")
        return

    if not schemas_file.exists():
        logger.error(f"Schemas file not found: {schemas_file}")
        return

    # Parse files
    logger.info("Parsing categories.txt...")
    categories_data = parse_categories_file(categories_file)
    logger.info(f"Parsed {len(categories_data)} categories")

    logger.info("Parsing schemas.txt...")
    schemas_data, category_mappings = parse_schemas_file(schemas_file)
    logger.info(f"Parsed {len(schemas_data)} schemas")

    # Seed database
    async with async_session() as db:
        await seed_categories(db, categories_data)
        await seed_schemas(db, schemas_data, category_mappings)

    logger.info("Seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
