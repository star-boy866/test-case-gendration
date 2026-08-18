"""
Risk Analyzer for Comprehensive Test Mode.
Derives implicit risks (Security, Performance) from requirements or metadata.
"""

from app.domain.cognos_requirement import CognosRequirement
from app.domain.cognos_comprehensive_models import Risk
from app.domain.cognos_test_case import CognosTestCase, TestType, TestCasePriority
from app.domain.cognos_requirement import TestOrigin

def derive_risks(requirements: list[CognosRequirement]) -> list[Risk]:
    """Identify implicit risks from the specification."""
    risks = []
    has_pii = False
    
    for req in requirements:
        text = (req.requirement_text + " " + req.business_label + " " + req.field).lower()
        if "ssn" in text or "phi" in text or "pii" in text or "patient" in text:
            has_pii = True
            break
            
    if has_pii:
        risks.append(Risk(
            risk_id="RISK-SEC-01",
            description="Report contains PII/PHI. Potential security/EDMS risk if distributed improperly.",
            impact="High",
            derived_from="Inferred from fields containing SSN/PHI/Patient data"
        ))
        
    return risks

def generate_risk_tests(risk: Risk) -> list[CognosTestCase]:
    """Generate mitigating test cases for identified risks."""
    tests = []
    if "PII" in risk.description or "PHI" in risk.description:
        tests.append(CognosTestCase(
            test_case_id=f"TEST-{risk.risk_id}",
            report_id="UNKNOWN", # Will be patched by engine
            test_case_title=f"Security Validation - {risk.risk_id}",
            category="SPECIAL_PROCESSING",
            requirement_ids=[],
            objective="Verify that PII/PHI data is only accessible to authorized users and masked if required.",
            source_section="Security Policies",
            test_steps="1. Login as unauthorized user\n2. Attempt to view report\n3. Verify access denied or data masked",
            expected_result="User cannot access unauthorized PII/PHI data.",
            test_type=TestType.SECURITY,
            origin=TestOrigin.RISK_DERIVED,
            priority=TestCasePriority.CRITICAL
        ))
    return tests
