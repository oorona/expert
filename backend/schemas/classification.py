"""Classification JSON schema for category classification."""

CLASSIFICATION_SCHEMA = {
    "type": "object",
    "required": ["categories", "primary_intent"],
    "properties": {
        "primary_intent": {
            "type": "string",
            "description": "Single sentence describing the user's primary intent"
        },
        "categories": {
            "type": "array",
            "description": "1-3 most relevant categories, ordered by confidence (highest first)",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["category", "confidence", "reasoning"],
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "Incident_Diagnostic",
                            "Inventory_Discovery",
                            "Impact_Analysis",
                            "Performance_Tuning",
                            "Procedural_HowTo",
                            "Code_Generation",
                            "Concept_Education",
                            "Security_Compliance",
                            "Capacity_Planning",
                            "Operational_Status",
                            "Architecture_Design",
                            "Backup_Recovery",
                            "Patching_Lifecycle",
                            "Data_Movement",
                            "Cost_Licensing",
                            "Network_Connectivity",
                            "Concurrency_Locking",
                            "Job_Scheduling",
                            "Configuration_Drift",
                            "Cloud_Infrastructure"
                        ],
                        "description": "The category name"
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Confidence score between 0 and 1"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation (1-2 sentences) why this category was chosen based on keywords or patterns in the user input"
                    }
                }
            }
        },
        "extracted_entities": {
            "type": "object",
            "description": "Key entities extracted from the input",
            "properties": {
                "error_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Error codes found (e.g., ORA-00600, HTTP 502)"
                },
                "system_components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "System components mentioned (e.g., listener, tablespace, database)"
                },
                "technologies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Technologies or products mentioned (e.g., Oracle, RMAN, AWS)"
                },
                "action_verbs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key action verbs indicating intent (e.g., fix, check, explain, create)"
                }
            }
        }
    }
}
