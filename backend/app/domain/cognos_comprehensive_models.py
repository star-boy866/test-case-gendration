"""
Domain models for Comprehensive Test Design Mode.
Includes Risk, Assumption, and Methodology entities.
"""

from pydantic import BaseModel, Field
from typing import Optional

class Risk(BaseModel):
    """Identified risk (e.g., Security, Performance) derived from the specification."""
    risk_id: str = ""
    description: str = ""
    impact: str = "Medium" # High, Medium, Low
    derived_from: str = ""
    mitigating_test_case_ids: list[str] = Field(default_factory=list)


class Assumption(BaseModel):
    """Identified assumption or dependency."""
    assumption_id: str = ""
    description: str = ""
    dependency: str = ""
    status: str = "Open"
    validating_test_case_ids: list[str] = Field(default_factory=list)


class Methodology(BaseModel):
    """Methodology documentation for the generated test suite."""
    description: str = ""
    techniques_used: list[str] = Field(default_factory=list)
    rules_applied: list[str] = Field(default_factory=list)
