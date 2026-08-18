"""
Cognos logic interpreter using LLMs.

Used strictly for targeted interpretation of complex processing rules,
NOT for deciding what to test or orchestrating the pipeline.

The deterministic rule engine handles all structural mapping. This module
is called when a column has a processing rule that is complex enough that
an LLM can provide better test steps/descriptions than a generic template.
"""

from __future__ import annotations

import json
import re

from app.infrastructure.llm.llm_provider import get_llm_provider
from app.domain.cognos_models import ReportField

# V1 Prompt template
PROMPT_V1 = """You are an expert QA tester writing test steps for a Cognos Report.

Field: {field_name}
Business Label: {business_label}
Source: {source_table}.{source_column}
Processing Rule: {processing_rule}

Analyze the processing rule and provide specific test steps and expected results 
for a manual tester to verify this logic. Do not invent any data tables or rules 
not mentioned above.

Respond with ONLY a JSON object (no markdown, no prose) in this format:
{{
  "interpreted_objective": "A clear, concise objective of what is being tested",
  "specific_test_steps": "Numbered steps that specifically address the rule's logic",
  "specific_expected_result": "Exactly what the tester should see if the rule works",
  "recommended_test_data": "What kind of edge cases or data the tester needs to verify this rule"
}}
"""


class LLMInterpretationError(Exception):
    pass


def interpret_processing_rule(field: ReportField) -> dict:
    """
    Send a complex processing rule to the LLM for targeted interpretation.
    
    Returns a dict with interpreted fields, falling back to empty strings
    if the LLM fails or is unavailable.
    """
    if not field.processing_rule:
        return {}

    try:
        provider = get_llm_provider()
    except Exception:
        # LLM not configured/available — fail gracefully
        return {}
        
    prompt = PROMPT_V1.format(
        field_name=field.field_name,
        business_label=field.business_label or field.field_name,
        source_table=field.source_table or "N/A",
        source_column=field.source_column or "N/A",
        processing_rule=field.processing_rule
    )

    try:
        raw_response = provider.call(prompt)
        return _parse_json_response(raw_response)
    except Exception:
        # If the LLM fails, we just fall back to deterministic generation
        # (The rule engine does not require this LLM output to function)
        return {}


def _parse_json_response(raw: str) -> dict:
    """Extract and parse JSON from an LLM response."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {}
