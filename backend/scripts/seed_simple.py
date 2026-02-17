"""Simple seeding script with hardcoded data."""
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from db.session import async_session
from models.database import Category, Schema, SchemaCategory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 20 Categories with their metadata
CATEGORIES = [
    {
        "name": "Incident_Diagnostic",
        "display_name": "Incident / Diagnostic",
        "description": "Something is broken, throwing an error, or behaving unexpectedly",
        "intent_description": "User reports errors, failures, unexpected behavior",
        "example_inputs": ["I'm getting ORA-00600", "The backup job failed last night"],
        "key_outputs": ["Error Code", "Severity", "Root Cause", "Remediation Steps"]
    },
    {
        "name": "Inventory_Discovery",
        "display_name": "Inventory / Discovery",
        "description": "The user wants to know the current state or contents of the system",
        "intent_description": "User wants to list, discover, or inspect system objects",
        "example_inputs": ["List all invalid packages in schema HR", "What patch version are we running?"],
        "key_outputs": ["query_result", "summary_stats", "scope"]
    },
    {
        "name": "Impact_Analysis",
        "display_name": "Impact Analysis (What-If)",
        "description": "The user proposes a change and wants to know the consequences/risks before doing it",
        "intent_description": "User wants to understand impact before making changes",
        "example_inputs": ["What happens if I change pga_aggregate_target to 50GB?", "Can I drop index idx_cust_id?"],
        "key_outputs": ["risk_level", "dependencies", "side_effects", "restart_required"]
    },
    {
        "name": "Performance_Tuning",
        "display_name": "Performance Tuning",
        "description": "The system works, but it is slow or resource-heavy",
        "intent_description": "User reports performance issues or wants optimization",
        "example_inputs": ["Why is query 83aa76b taking 5 minutes?", "The CPU spiked at 9 AM"],
        "key_outputs": ["bottleneck", "metrics", "optimization_suggestion"]
    },
    {
        "name": "Procedural_HowTo",
        "display_name": "Procedural / How-To",
        "description": "The user needs a step-by-step guide to perform a specific task",
        "intent_description": "User needs procedural guidance",
        "example_inputs": ["How do I clone the production DB to test?", "Walk me through restoring a control file"],
        "key_outputs": ["prerequisites", "steps", "verification"]
    },
    {
        "name": "Code_Generation",
        "display_name": "Code Generation / Syntax",
        "description": "The user wants the system to write or correct specific SQL/PLSQL code",
        "intent_description": "User wants code written or fixed",
        "example_inputs": ["Write a script to kill all sessions for user BOB", "Fix the syntax error in this trigger"],
        "key_outputs": ["code_block", "explanation", "safety_warning"]
    },
    {
        "name": "Concept_Education",
        "display_name": "Concept / Education",
        "description": "The user lacks domain knowledge and wants a definition or theoretical explanation",
        "intent_description": "User wants to learn concepts or features",
        "example_inputs": ["What is the difference between a heap table and an IOT?", "Explain 'Snapshot too old'"],
        "key_outputs": ["definition", "analogy", "best_use_case"]
    },
    {
        "name": "Security_Compliance",
        "display_name": "Security / Compliance",
        "description": "Questions regarding permissions, users, audit trails, or vulnerability",
        "intent_description": "User has security or compliance questions",
        "example_inputs": ["Who has ALTER SYSTEM privileges?", "Is TDE encryption enabled?"],
        "key_outputs": ["compliance_status", "vulnerability_list", "audit_evidence"]
    },
    {
        "name": "Capacity_Planning",
        "display_name": "Capacity Planning",
        "description": "Forward-looking questions about storage, growth, or resource limits",
        "intent_description": "User wants capacity forecasts",
        "example_inputs": ["When will the DATA tablespace fill up?", "Do we have space for a 2TB import?"],
        "key_outputs": ["forecast", "current_utilization", "growth_rate"]
    },
    {
        "name": "Operational_Status",
        "display_name": "Operational Status / Health",
        "description": "High-level check on system availability and pulse",
        "intent_description": "User wants health check or status",
        "example_inputs": ["Is the listener up?", "Are the standby databases in sync?"],
        "key_outputs": ["status", "lag/latency", "uptime"]
    },
    {
        "name": "Architecture_Design",
        "display_name": "Architecture & Design",
        "description": "User is planning a new system, designing a schema, or configuring HA",
        "intent_description": "User needs architectural guidance",
        "example_inputs": ["Should I use a Star Schema or Snowflake?", "Best way to set up Active Data Guard?"],
        "key_outputs": ["recommended_pattern", "pros_and_cons", "visual_representation"]
    },
    {
        "name": "Backup_Recovery",
        "display_name": "Backup & Disaster Recovery",
        "description": "User is configuring backups, checking validity, or initiating restore",
        "intent_description": "User has backup/restore needs",
        "example_inputs": ["Can we recover table ORDERS to yesterday 5PM?", "Is our RMAN backup meeting RPO?"],
        "key_outputs": ["feasibility", "recovery_window", "required_artifacts"]
    },
    {
        "name": "Patching_Lifecycle",
        "display_name": "Patching & Lifecycle Management",
        "description": "Questions about versioning, upgrades, EOL support, and applying patches",
        "intent_description": "User has patching or upgrade questions",
        "example_inputs": ["Prerequisites for October 2023 RU?", "When does Oracle 19c extended support end?"],
        "key_outputs": ["version_info", "compatibility_matrix", "estimated_downtime"]
    },
    {
        "name": "Data_Movement",
        "display_name": "Data Movement & Migration",
        "description": "User needs to move large volumes of data in, out, or across environments",
        "intent_description": "User needs data migration guidance",
        "example_inputs": ["Fastest way to export 500GB schema to AWS?", "How to set up GoldenGate?"],
        "key_outputs": ["tool_recommendation", "performance_parameters", "data_mapping_risks"]
    },
    {
        "name": "Cost_Licensing",
        "display_name": "Cost & Licensing Optimization",
        "description": "User wants to understand the financial impact of a technical decision",
        "intent_description": "User has cost or licensing questions",
        "example_inputs": ["How much will Advanced Compression cost?", "Can we scale down OCPUs on weekend?"],
        "key_outputs": ["licensing_impact", "estimated_cost_change", "optimization_alternative"]
    },
    {
        "name": "Network_Connectivity",
        "display_name": "Network & Connectivity",
        "description": "Database is healthy but applications/users cannot reach it",
        "intent_description": "User has connectivity issues",
        "example_inputs": ["Why ORA-12154: TNS could not resolve?", "Is listener accepting on port 1521?"],
        "key_outputs": ["connection_path", "listener_status", "diagnostic_test"]
    },
    {
        "name": "Concurrency_Locking",
        "display_name": "Concurrency & Locking",
        "description": "Sessions are blocking each other fighting for the same rows/resources",
        "intent_description": "User has locking or blocking issues",
        "example_inputs": ["Who is locking the EMPLOYEES table?", "Find root blocking session"],
        "key_outputs": ["blocking_tree", "lock_type", "resolution_action"]
    },
    {
        "name": "Job_Scheduling",
        "display_name": "Job Scheduling & Automation",
        "description": "Troubleshooting or managing database cron jobs and maintenance windows",
        "intent_description": "User has scheduler or automation questions",
        "example_inputs": ["Why didn't stats job run last night?", "Create schedule for stored procedure"],
        "key_outputs": ["job_status", "run_history", "next_run_time"]
    },
    {
        "name": "Configuration_Drift",
        "display_name": "Configuration Drift & Baselines",
        "description": "User wants to compare current state against baseline or different environment",
        "intent_description": "User wants configuration comparison",
        "example_inputs": ["What parameters differ between Node 1 and 2?", "Did someone change spfile?"],
        "key_outputs": ["drift_delta", "modified_by", "rollback_command"]
    },
    {
        "name": "Cloud_Infrastructure",
        "display_name": "Cloud & Infrastructure Provisioning",
        "description": "Dealing with host, storage mounts, or cloud control plane actions",
        "intent_description": "User needs cloud/infrastructure help",
        "example_inputs": ["Attach new block volume to ASM?", "Scale up Autonomous Database"],
        "key_outputs": ["infrastructure_layer", "cli_payload", "downtime_implication"]
    }
]

# Read JSON schemas from specs files
def load_schemas_from_files():
    """Load the 5 JSON schemas from specs/schemas.txt."""
    specs_path = Path(__file__).parent.parent / "specs" / "schemas.txt"

    if not specs_path.exists():
        logger.error(f"Schemas file not found: {specs_path}")
        return []

    content = specs_path.read_text()

    # Manually extract the 5 schemas (simplified approach)
    schemas = []

    # Schema 1: Fixer (The Fixer Schema)
    schemas.append({
        "name": "Fixer",
        "description": "For incident diagnostics, errors, and problem-solving",
        "categories": ["Incident_Diagnostic", "Concurrency_Locking", "Network_Connectivity", "Job_Scheduling", ("Performance_Tuning", 1)],
        "json_path": "schemas/fixer.json"  # We'll create these
    })

    # Schema 2: Analyst
    schemas.append({
        "name": "Analyst",
        "description": "For impact analysis and planning",
        "categories": ["Impact_Analysis", "Capacity_Planning", "Cost_Licensing", "Architecture_Design"],
        "json_path": "schemas/analyst.json"
    })

    # Schema 3: Guide
    schemas.append({
        "name": "Guide",
        "description": "For procedures and how-to guides",
        "categories": ["Procedural_HowTo", "Code_Generation", "Data_Movement", "Backup_Recovery"],
        "json_path": "schemas/guide.json"
    })

    # Schema 4: Inspector
    schemas.append({
        "name": "Inspector",
        "description": "For discovery and status checks",
        "categories": ["Inventory_Discovery", "Operational_Status", "Configuration_Drift", ("Performance_Tuning", 2)],
        "json_path": "schemas/inspector.json"
    })

    # Schema 5: Teacher
    schemas.append({
        "name": "Teacher",
        "description": "For education and compliance",
        "categories": ["Concept_Education", "Security_Compliance", "Patching_Lifecycle", "Cloud_Infrastructure"],
        "json_path": "schemas/teacher.json"
    })

    return schemas


async def main():
    logger.info("Starting simple database seeding...")

    async with async_session() as db:
        # Seed categories
        logger.info(f"Seeding {len(CATEGORIES)} categories...")
        for cat_data in CATEGORIES:
            result = await db.execute(
                select(Category).where(Category.name == cat_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(f"  Category {cat_data['name']} already exists")
            else:
                category = Category(**cat_data)
                db.add(category)
                logger.info(f"  Added category: {cat_data['name']}")

        await db.commit()
        logger.info("Categories seeded successfully!")

        # Seed schemas
        logger.info("Seeding schemas...")
        schemas_data = load_schemas_from_files()

        for schema_data in schemas_data:
            result = await db.execute(
                select(Schema).where(Schema.name == schema_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(f"  Schema {schema_data['name']} already exists")
                schema = existing
            else:
                # Use a simple placeholder schema - can be updated later via API
                placeholder_schema = {"type": "object", "properties": {}}
                schema = Schema(
                    name=schema_data["name"],
                    description=schema_data["description"],
                    json_schema=placeholder_schema
                )
                db.add(schema)
                await db.flush()
                logger.info(f"  Added schema: {schema_data['name']} (id={schema.id})")

            # Add category mappings
            for cat in schema_data["categories"]:
                if isinstance(cat, tuple):
                    cat_name, priority = cat
                else:
                    cat_name, priority = cat, 1

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
        logger.info("Schemas seeded successfully!")

    logger.info("✅ Seeding completed!")


if __name__ == "__main__":
    asyncio.run(main())
