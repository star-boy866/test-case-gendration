"""
Requirement Analyzer for Comprehensive Test Mode.
Processes reviewer comments to classify them into RISK, OPEN_REVIEW_ITEM, or CONTRADICTION.
"""

from app.domain.cognos_requirement import CognosRequirement
from app.domain.cognos_test_case import CognosTestCase, TestType, TestCasePriority
from app.domain.cognos_requirement import TestOrigin

def analyze_comments(comments: list[dict], requirements: list[CognosRequirement]) -> list[CognosTestCase]:
    """Analyze reviewer comments and generate COMMENT_DERIVED tests if appropriate."""
    tests = []
    for i, comment in enumerate(comments):
        text = comment.get('text', '').lower()
        author = comment.get('author', 'Reviewer')
        
        category = "OPEN_REVIEW_ITEM"
        if any(kw in text for kw in ["risk", "security", "performance", "pii", "phi"]):
            category = "RISK"
        elif "contradict" in text or "conflict" in text or "wrong" in text:
            category = "CONTRADICTION"
            
        tests.append(CognosTestCase(
            test_case_id=f"COM-{i+1:03d}",
            report_id="UNKNOWN", # Will be patched
            test_case_title=f"Review Comment - {category}",
            category="SPECIAL_PROCESSING",
            requirement_ids=[],
            objective=f"Verify resolution of reviewer comment: '{comment.get('text', '')}'",
            source_section="Review Comments",
            test_steps="1. Review design specification\n2. Ensure comment is addressed in implementation",
            expected_result="Comment is resolved and system behaves as agreed.",
            test_type=TestType.VALIDATION,
            origin=TestOrigin.COMMENT_DERIVED,
            priority=TestCasePriority.HIGH if category in ["RISK", "CONTRADICTION"] else TestCasePriority.LOW,
            notes=f"Author: {author}, Classified as: {category}"
        ))
        
    return tests
