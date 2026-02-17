"""Update schemas with correct JSON from specs."""
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from db.session import async_session
from models.database import Schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Complete JSON schemas from specs/schemas.txt
SCHEMAS_JSON = {
    "Fixer": {
        "type": "object",
        "required": [
            "title",
            "error_summary",
            "root_cause",
            "severity",
            "affected_systems",
            "resolution_steps",
            "preventive_measures",
            "visual_aid_suggested"
        ],
        "properties": {
            "title": {
                "type": "string",
                "description": "A concise, human-friendly knowledge-base article title (max 80 chars). Must describe the PROBLEM and SOLUTION area, not the raw error. NEVER include timestamps, dates, SQL statements, file paths, trace file names, or raw error text. Good examples: 'Resolving ORA-04031 Shared Pool Memory Allocation Failure', 'Troubleshooting ORA-01555 Snapshot Too Old During Long-Running Queries', 'Fixing Nginx 502 Bad Gateway After Upstream Timeout'. Bad examples: 'Tue Feb 17 09:12:44 2026 ORA-04031...', 'Error in /u01/app/oracle/...', 'SELECT SUM(ORDER_TOTAL) FROM...'"
            },
            "severity": {
                "enum": ["critical", "high", "medium", "low"],
                "type": "string",
                "description": "Severity level: critical, high, medium, or low"
            },
            "root_cause": {
                "type": "string",
                "description": "Detailed explanation of the root cause"
            },
            "error_summary": {
                "type": "string",
                "description": "A concise one-line summary of the error"
            },
            "additional_notes": {
                "type": "string",
                "description": "Any extra context, warnings, or related information"
            },
            "affected_systems": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of systems or components affected by this error"
            },
            "resolution_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["action", "command"],
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "Brief description of what this step accomplishes (1-2 sentences)"
                        },
                        "command": {
                            "type": "string",
                            "description": "The EXACT executable command, SQL statement, config change, or CLI invocation for this step. Must be copy-paste ready. Use code formatting. For config changes show the full parameter line. NEVER leave this empty."
                        }
                    }
                },
                "description": "Ordered list of resolution steps. Each step MUST have an 'action' explaining what to do AND a 'command' with the exact executable command/SQL/config. Never provide an action without its corresponding command."
            },
            "preventive_measures": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["action", "command"],
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "Brief description of the preventive measure"
                        },
                        "command": {
                            "type": "string",
                            "description": "The exact command, script, cron entry, monitoring query, or configuration to implement this measure. Must be copy-paste ready."
                        }
                    }
                },
                "description": "Preventive measures to avoid recurrence. Each must include an 'action' and a 'command' with the exact monitoring query, alert config, cron job, or parameter change."
            },
            "visual_aid_suggested": {
                "type": "boolean",
                "description": "Whether a visual diagram/infographic would help illustrate this problem"
            },
            "image_generation_prompt": {
                "type": "string",
                "description": "If visual_aid_suggested is true, provide a detailed, comprehensive prompt (200-400 words) for generating a technical infographic. Include specific details about diagram type, components, connections, colors, labels, and layout. Should be detailed enough for an AI image generator to create an accurate technical diagram."
            }
        }
    },
    "Analyst": {
        "type": "object",
        "required": [
            "title",
            "analysis_summary",
            "risk_level",
            "downtime_required",
            "impact_details",
            "alternatives",
            "visual_aid_suggested"
        ],
        "properties": {
            "title": {
                "type": "string",
                "description": "A concise title summarizing the proposed change or analysis (max 80 chars)."
            },
            "analysis_summary": {
                "type": "string",
                "description": "A 1-2 sentence executive summary of what this change/plan will accomplish and its primary consequence."
            },
            "risk_level": {
                "enum": ["high", "medium", "low"],
                "type": "string",
                "description": "The overall risk of implementing this change."
            },
            "downtime_required": {
                "type": "boolean",
                "description": "True if this operation requires taking the system offline or restarting instances."
            },
            "impact_details": {
                "type": "object",
                "required": ["performance", "financial", "dependencies"],
                "properties": {
                    "performance": {
                        "type": "string",
                        "description": "Expected impact on CPU, I/O, memory, or query latency."
                    },
                    "financial": {
                        "type": "string",
                        "description": "Expected changes to licensing, cloud compute costs, or storage costs."
                    },
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of systems, schemas, or applications that rely on the component being changed."
                    }
                }
            },
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["approach", "pros", "cons"],
                    "properties": {
                        "approach": {"type": "string", "description": "Name of the alternative method."},
                        "pros": {"type": "string", "description": "Why this alternative is good."},
                        "cons": {"type": "string", "description": "Drawbacks of this alternative."}
                    }
                },
                "description": "At least one alternative way to achieve the same goal."
            },
            "rollback_plan": {
                "type": "string",
                "description": "The exact command or process to revert this change if it fails. Must be highly specific."
            },
            "visual_aid_suggested": {
                "type": "boolean",
                "description": "Whether an architecture or topology diagram would help illustrate this plan."
            },
            "image_generation_prompt": {
                "type": "string",
                "description": "If visual_aid_suggested is true, provide a detailed prompt (200-400 words) for generating an architecture or topology diagram."
            }
        }
    },
    "Guide": {
        "type": "object",
        "required": [
            "title",
            "task_overview",
            "complexity",
            "estimated_time_minutes",
            "prerequisites",
            "execution_steps",
            "verification_steps",
            "visual_aid_suggested"
        ],
        "properties": {
            "title": {
                "type": "string",
                "description": "A concise, action-oriented title for the procedure (e.g., 'Cloning a Pluggable Database', 'Exporting Schema via Data Pump')."
            },
            "task_overview": {
                "type": "string",
                "description": "Brief summary of the procedure's goal."
            },
            "complexity": {
                "enum": ["basic", "intermediate", "advanced"],
                "type": "string",
                "description": "Skill level required to execute this safely."
            },
            "estimated_time_minutes": {
                "type": "integer",
                "description": "Rough estimate of how long the procedure takes to run."
            },
            "prerequisites": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Conditions that must be met before starting (e.g., 'Target DB must be in MOUNT state')."
            },
            "execution_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["step_description", "command", "expected_output"],
                    "properties": {
                        "step_description": {"type": "string", "description": "Clear explanation of what this step does."},
                        "command": {"type": "string", "description": "The EXACT executable code, SQL, or CLI command. Copy-paste ready."},
                        "expected_output": {"type": "string", "description": "What the system should return if the command succeeds."}
                    }
                },
                "description": "Ordered, sequential steps to complete the task."
            },
            "verification_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["action", "command"],
                    "properties": {
                        "action": {"type": "string", "description": "What we are verifying."},
                        "command": {"type": "string", "description": "The query or command to verify success."}
                    }
                },
                "description": "Steps to prove the procedure worked."
            },
            "visual_aid_suggested": {
                "type": "boolean",
                "description": "Whether a flow chart would help."
            },
            "image_generation_prompt": {
                "type": "string",
                "description": "Detailed prompt for generating a flowchart or step-by-step process diagram."
            }
        }
    },
    "Inspector": {
        "type": "object",
        "required": [
            "title",
            "inspection_summary",
            "overall_health",
            "findings",
            "visual_aid_suggested"
        ],
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the report (e.g., 'AWR Performance Analysis', 'Invalid Object Inventory')."
            },
            "inspection_summary": {
                "type": "string",
                "description": "High-level summary of what was found during the inspection."
            },
            "overall_health": {
                "enum": ["healthy", "degraded", "down", "unknown"],
                "type": "string",
                "description": "Current state of the inspected target."
            },
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["item_name", "current_value"],
                    "properties": {
                        "item_name": {"type": "string", "description": "The metric, parameter, or object found."},
                        "current_value": {"type": "string", "description": "The actual value or status observed."},
                        "expected_value": {"type": "string", "description": "The baseline or recommended value (if applicable)."},
                        "notes": {"type": "string", "description": "Why this finding matters."}
                    }
                },
                "description": "The raw data payload, list of objects, or parameter diffs."
            },
            "tuning_recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["action", "command"],
                    "properties": {
                        "action": {"type": "string", "description": "What to change to fix a degraded finding."},
                        "command": {"type": "string", "description": "The SQL/CLI command to apply the tune."}
                    }
                },
                "description": "Actionable fixes for any negative findings."
            },
            "visual_aid_suggested": {
                "type": "boolean",
                "description": "Whether a chart or dashboard mockup would help."
            },
            "image_generation_prompt": {
                "type": "string",
                "description": "Detailed prompt for generating a chart (pie/bar/line) or dashboard layout visualizing the findings."
            }
        }
    },
    "Teacher": {
        "type": "object",
        "required": [
            "title",
            "concept_term",
            "simple_definition",
            "technical_definition",
            "use_cases",
            "official_references",
            "visual_aid_suggested"
        ],
        "properties": {
            "title": {
                "type": "string",
                "description": "The topic being explained (e.g., 'Understanding Transparent Data Encryption', 'Oracle 19c Patching Lifecycle')."
            },
            "concept_term": {
                "type": "string",
                "description": "The specific feature, rule, or concept requested."
            },
            "simple_definition": {
                "type": "string",
                "description": "An ELI5 (Explain Like I'm 5) analogy or plain-english description."
            },
            "technical_definition": {
                "type": "string",
                "description": "The highly technical, deep-dive explanation of how it works under the hood."
            },
            "use_cases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["scenario", "why_it_fits"],
                    "properties": {
                        "scenario": {"type": "string", "description": "A real-world business or technical scenario."},
                        "why_it_fits": {"type": "string", "description": "Why this concept/feature is the right choice for the scenario."}
                    }
                },
                "description": "When and why to use this feature."
            },
            "compliance_rules": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Any strict rules, licensing constraints, or security implications to be aware of."
            },
            "official_references": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["doc_title", "url"],
                    "properties": {
                        "doc_title": {"type": "string", "description": "Title of the Oracle Doc or MOS Note."},
                        "url": {"type": "string", "description": "A valid URL or Support ID."}
                    }
                },
                "description": "Links for further reading."
            },
            "visual_aid_suggested": {
                "type": "boolean",
                "description": "Whether an infographic would help explain the concept."
            },
            "image_generation_prompt": {
                "type": "string",
                "description": "Detailed prompt for generating an educational infographic explaining the theory or mechanics of the concept."
            }
        }
    }
}


async def main():
    logger.info("Updating schemas with correct JSON...")

    async with async_session() as db:
        for schema_name, schema_json in SCHEMAS_JSON.items():
            result = await db.execute(
                select(Schema).where(Schema.name == schema_name)
            )
            schema = result.scalar_one_or_none()

            if schema:
                schema.json_schema = schema_json
                logger.info(f"  ✓ Updated {schema_name} schema")
            else:
                logger.warning(f"  ✗ Schema {schema_name} not found in database")

        await db.commit()

    logger.info("✅ Schema update completed!")


if __name__ == "__main__":
    asyncio.run(main())
