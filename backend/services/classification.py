"""Classification service for categorizing user input and selecting appropriate schemas."""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Category, Schema, SchemaCategory
from prompts.classification_prompt import (
    CLASSIFICATION_SYSTEM_PROMPT,
    CLASSIFICATION_USER_PROMPT,
)
from schemas.classification import CLASSIFICATION_SCHEMA
from services.gemini import gemini_service

logger = logging.getLogger(__name__)


class ClassificationService:
    """Service for classifying user input into categories and selecting schemas."""

    async def classify_input(
        self,
        user_input: str,
        db: AsyncSession,
        model: str = "gemini-2.5-flash",
    ) -> dict:
        """Classify user input into 1-3 categories using Gemini.

        Args:
            user_input: The user's question or problem description
            db: Database session
            model: Gemini model to use for classification

        Returns:
            Classification result dict with:
            - primary_intent: str
            - categories: list[dict] with category, confidence, reasoning
            - extracted_entities: dict with error_codes, system_components, etc.
        """
        # Build categories description for prompt
        categories_desc = await self._build_categories_description(db)

        # Format prompts
        system_prompt = CLASSIFICATION_SYSTEM_PROMPT.format(
            categories_description=categories_desc
        )
        user_prompt = CLASSIFICATION_USER_PROMPT.format(user_input=user_input)

        # Call Gemini with classification schema
        logger.info(f"Classifying input (length={len(user_input)}) with model {model}")

        result = await gemini_service.diagnose_error(
            error_text=user_input,
            image_bytes=None,
            image_mime=None,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=CLASSIFICATION_SCHEMA,
            model=model,
            temperature=0.3,  # Lower temperature for more consistent classification
            thinking_level="off",  # No extended thinking needed for classification
            use_grounding=False,  # No web search for classification
            use_file_search=False,  # No RAG for classification
            file_search_store_names=None,
        )

        classification = result["raw_json"]

        # Log classification result
        if classification.get("categories"):
            primary_cat = classification["categories"][0]
            logger.info(
                f"Classified as: {primary_cat['category']} "
                f"(confidence={primary_cat['confidence']:.2f})"
            )

        return classification

    async def select_schema(
        self, classification_result: dict, db: AsyncSession
    ) -> tuple[int, str]:
        """Select appropriate schema based on classification result.

        Args:
            classification_result: Classification dict from classify_input()
            db: Database session

        Returns:
            Tuple of (schema_id, schema_name)

        Raises:
            ValueError: If no categories found or no schema available
        """
        categories = classification_result.get("categories", [])
        if not categories:
            raise ValueError("No categories in classification result")

        # Get primary category (first in list, highest confidence)
        primary_category = categories[0]["category"]
        primary_reasoning = categories[0].get("reasoning", "").lower()

        logger.info(f"Selecting schema for primary category: {primary_category}")

        # Special handling for Performance_Tuning (appears in both Fixer and Inspector)
        if primary_category == "Performance_Tuning":
            # Check reasoning for intent keywords
            inspection_keywords = [
                "check",
                "analyze",
                "baseline",
                "health",
                "awr",
                "inspect",
                "status",
                "report",
                "review",
            ]
            problem_keywords = [
                "slow",
                "fix",
                "tune",
                "optimize",
                "bottleneck",
                "issue",
                "problem",
            ]

            # Count keyword occurrences
            inspection_score = sum(
                1 for kw in inspection_keywords if kw in primary_reasoning
            )
            problem_score = sum(1 for kw in problem_keywords if kw in primary_reasoning)

            if inspection_score > problem_score:
                # Prefer Inspector (priority=2)
                priority_order = [2, 1]
                logger.info("Performance_Tuning: Inspection-focused, preferring Inspector")
            else:
                # Prefer Fixer (priority=1) - default for action-oriented queries
                priority_order = [1, 2]
                logger.info("Performance_Tuning: Problem-focused, preferring Fixer")
        else:
            # Normal priority
            priority_order = [1]

        # Query for schema associated with this category, trying priorities in order
        for priority in priority_order:
            stmt = (
                select(Schema, SchemaCategory)
                .join(SchemaCategory, Schema.id == SchemaCategory.schema_id)
                .where(
                    SchemaCategory.category_name == primary_category,
                    SchemaCategory.priority == priority,
                    Schema.is_active == True,
                )
                .limit(1)
            )
            result = await db.execute(stmt)
            row = result.first()

            if row:
                schema, _ = row
                logger.info(
                    f"Selected schema: {schema.name} (id={schema.id}, priority={priority})"
                )
                return schema.id, schema.name

        # Fallback: try any active schema for this category (ignore priority)
        stmt = (
            select(Schema, SchemaCategory)
            .join(SchemaCategory, Schema.id == SchemaCategory.schema_id)
            .where(
                SchemaCategory.category_name == primary_category,
                Schema.is_active == True,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        row = result.first()

        if row:
            schema, _ = row
            logger.warning(
                f"Using fallback schema for {primary_category}: {schema.name}"
            )
            return schema.id, schema.name

        # No schema found for this category
        raise ValueError(
            f"No active schema found for category: {primary_category}. "
            "Please check schema_categories mappings."
        )

    async def _build_categories_description(self, db: AsyncSession) -> str:
        """Build formatted description of all categories for the classification prompt.

        Args:
            db: Database session

        Returns:
            Formatted string with category descriptions
        """
        stmt = select(Category).order_by(Category.name)
        result = await db.execute(stmt)
        categories = result.scalars().all()

        lines = []
        for i, cat in enumerate(categories, 1):
            lines.append(f"{i}. **{cat.display_name}** ({cat.name})")
            lines.append(f"   Intent: {cat.intent_description}")

            if cat.example_inputs and len(cat.example_inputs) > 0:
                examples = ", ".join(f'"{ex}"' for ex in cat.example_inputs[:2])
                lines.append(f"   Examples: {examples}")

            if cat.key_outputs and len(cat.key_outputs) > 0:
                outputs = ", ".join(cat.key_outputs[:3])
                lines.append(f"   Key Outputs: {outputs}")

            lines.append("")  # Blank line between categories

        return "\n".join(lines)


# Global instance
classification_service = ClassificationService()
