"""
Final presentation composition model for Excel reporting.

This model combines the strictly isolated outputs of the DSD-driven Rule Engine
and the XML-driven Traceability Engine so they can be rendered side-by-side
in the final Excel audit workbook, without structurally coupling test case
discovery to the Cognos implementation.
"""
from typing import Optional
from pydantic import BaseModel

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import RequirementSet
from app.domain.cognos_test_case import TestSuite
from app.domain.traceability_models import TraceabilityResult

class FinalReportContext(BaseModel):
    """
    Composition root for final Excel reporting.
    Exists only to compose final reporting information.
    """
    report_definition: ReportDefinition
    requirement_set: RequirementSet
    test_suite: TestSuite
    traceability_result: Optional[TraceabilityResult] = None
