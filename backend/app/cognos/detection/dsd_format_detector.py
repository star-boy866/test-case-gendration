"""
DSD Format Detector.

Lightweight structural and identifying-marker analyzer to detect DSD format
profiles (NH, ND, AK) prior to pipeline execution.
"""

from enum import Enum
from pathlib import Path
from typing import List, Optional
import re
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DSDProfile(str, Enum):
    AUTO = "AUTO"
    NH = "NH"
    ND = "ND"
    AK = "AK"
    UNKNOWN = "UNKNOWN"


class DetectionConfidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    NONE = "None"


class DetectionState(str, Enum):
    DETECTING = "DETECTING"
    DETECTED = "DETECTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNKNOWN = "UNKNOWN"


class DSDDetectionResult(BaseModel):
    detected_format: str
    confidence: str
    display_name: str
    description: str
    matched_markers: List[str]
    status: str
    message: Optional[str] = None


# Marker dictionaries for each profile
_PROFILE_MARKERS = {
    DSDProfile.ND: {
        "strong": [
            "north dakota medicaid systems project",
            "north dakota mmis",
            "north dakota department of human services",
            "state of north dakota",
            "tpl rejection error handling report",
            "nd medicaid systems",
            "nd mmis report definition",
            "nd mmis",
        ],
        "weak": [
            "north dakota",
            "nd report layout",
            "nd report specification",
        ],
        "display_name": "ND — North Dakota",
        "description": "North Dakota Medicaid Systems Project MMIS DSD",
    },
    DSDProfile.NH: {
        "strong": [
            "nh mmis report definition",
            "nh mmis report layout",
            "nh mmis report specification",
            "new hampshire department of health and human services",
            "nh mmis",
            "p_rpt_cldi_term_tb",
            "p_rpt_cldi_err_tb",
            "nh mmis report",
            "new hampshire dhhs",
        ],
        "weak": [
            "new hampshire",
            "dhhs",
            "oplc",
        ],
        "display_name": "NH — New Hampshire",
        "description": "New Hampshire MMIS DSD",
    },
    DSDProfile.AK: {
        "strong": [
            "alaska cognos dsd",
            "alaska department of health",
            "state of alaska mmis",
            "alaska mmis report",
            "alaska mmis",
            "ak cognos dsd",
            "ak mmis",
        ],
        "weak": [
            "alaska",
            "state of alaska",
        ],
        "display_name": "AK — Alaska",
        "description": "Alaska Cognos DSD",
    },
}


class DSDFormatDetector:
    """
    Analyzes DOCX text, table headings, and metadata to classify DSD profiles.
    """

    @classmethod
    def detect_format(
        cls,
        doc_path: Path,
        doc_name: Optional[str] = None,
    ) -> DSDDetectionResult:
        """
        Inspect document structure and identifying markers.
        """
        extracted_text_blocks: List[str] = []

        if doc_name:
            extracted_text_blocks.append(doc_name.lower())

        if doc_path.exists() and doc_path.is_file():
            try:
                import docx
                doc = docx.Document(str(doc_path))

                # Extract first 50 paragraphs
                for p in doc.paragraphs[:50]:
                    txt = p.text.strip().lower()
                    if txt:
                        extracted_text_blocks.append(txt)

                # Extract table headers & first rows from first 10 tables
                for t in doc.tables[:10]:
                    for r in t.rows[:5]:
                        row_txt = " ".join(c.text.strip().lower() for c in r.cells if c.text.strip())
                        if row_txt:
                            extracted_text_blocks.append(row_txt)

                # Extract document headers/footers if present
                for section in doc.sections[:3]:
                    if section.header:
                        for p in section.header.paragraphs:
                            if p.text.strip():
                                extracted_text_blocks.append(p.text.strip().lower())
            except Exception as e:
                logger.warning("Failed to parse docx for format detection: %s", e)

        full_corpus = " \n ".join(extracted_text_blocks)

        # Score profiles
        scores = {}
        matched_markers_map = {}

        for profile, data in _PROFILE_MARKERS.items():
            strong_matches = [m for m in data["strong"] if m in full_corpus]
            weak_matches = [m for m in data["weak"] if m in full_corpus]

            # Strong match: 3 points each; Weak match: 1 point each
            score = (len(strong_matches) * 3) + len(weak_matches)
            scores[profile] = score
            matched_markers_map[profile] = strong_matches + weak_matches

        # Find best candidate
        best_profile = max(scores, key=scores.get)
        best_score = scores[best_profile]
        best_markers = matched_markers_map[best_profile]

        if best_score >= 3:
            # Strong confidence
            profile_info = _PROFILE_MARKERS[best_profile]
            return DSDDetectionResult(
                detected_format=best_profile.value,
                confidence=DetectionConfidence.HIGH.value,
                display_name=profile_info["display_name"],
                description=profile_info["description"],
                matched_markers=best_markers,
                status=DetectionState.DETECTED.value,
                message=None,
            )
        elif best_score >= 1:
            # Low confidence
            profile_info = _PROFILE_MARKERS[best_profile]
            return DSDDetectionResult(
                detected_format=best_profile.value,
                confidence=DetectionConfidence.LOW.value,
                display_name=profile_info["display_name"],
                description=profile_info["description"],
                matched_markers=best_markers,
                status=DetectionState.LOW_CONFIDENCE.value,
                message=f"Possible match: {profile_info['display_name']} (Low Confidence). Please confirm or select manually.",
            )
        else:
            return DSDDetectionResult(
                detected_format=DSDProfile.UNKNOWN.value,
                confidence=DetectionConfidence.NONE.value,
                display_name="Unknown",
                description="Unable to determine DSD format.",
                matched_markers=[],
                status=DetectionState.UNKNOWN.value,
                message="Unable to determine DSD format. Please select NH / ND / AK manually.",
            )
