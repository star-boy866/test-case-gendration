"""
DSD Profile Dispatcher.

Routes uploaded Cognos DSD documents to the appropriate profile interpreter
(NH vs ND vs AK) while isolating state-specific parsing logic and preserving
frozen baseline behavior for New Hampshire.
"""

from pathlib import Path
from typing import Optional, Tuple, Any
import logging

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import RequirementSet
from app.cognos.detection.dsd_format_detector import DSDFormatDetector, DSDProfile
from app.services.cognos_docx_parser import parse_cognos_docx

logger = logging.getLogger(__name__)


def dispatch_and_interpret_dsd(
    docx_path: Path | str,
    source_document_name: str = "",
    dsd_profile: Optional[str] = "AUTO",
) -> Tuple[ReportDefinition, RequirementSet, Any]:
    """
    Dispatches a DSD document to the appropriate state-specific interpreter
    and returns canonical (ReportDefinition, RequirementSet, raw_dsd_ast).
    """
    path = Path(docx_path)
    doc_name = source_document_name or path.name

    effective_profile = (dsd_profile or "AUTO").upper().strip()

    # Step 1: Auto-detection if requested or default
    if effective_profile == "AUTO":
        detection = DSDFormatDetector.detect_format(path, doc_name)
        if detection.detected_format == DSDProfile.ND.value:
            effective_profile = "ND"
        elif detection.detected_format == DSDProfile.AK.value:
            effective_profile = "AK"
        else:
            effective_profile = "NH"

    # Step 2: Route to state-specific profile interpreter
    if effective_profile == "ND":
        logger.info(f"Routing document '{doc_name}' to North Dakota (ND) DSD pipeline.")
        from app.cognos.extraction.nd_mmis_dsd_interpreter import NdMmisDsdInterpreter
        from app.cognos.extraction.nd_mmis_requirement_builder import NdMmisRequirementBuilder
        from app.cognos.extraction.nd_mmis_dsd_mapper import map_nd_dsd_to_domain

        nd_interpreter = NdMmisDsdInterpreter(path)
        nd_dsd = nd_interpreter.interpret()
        nd_builder = NdMmisRequirementBuilder(nd_dsd)
        req_set = nd_builder.build()
        report_def = map_nd_dsd_to_domain(nd_dsd, doc_name)
        return report_def, req_set, nd_dsd

    elif effective_profile == "AK":
        raise NotImplementedError("Alaska (AK) DSD profile is not enabled yet.")

    else:
        # Default / NH: Exactly preserves the proven NH baseline pipeline
        logger.info(f"Routing document '{doc_name}' to New Hampshire (NH) baseline pipeline.")
        from app.cognos.extraction.nh_mmis_dsd_interpreter import NhMmisDsdInterpreter
        from app.cognos.extraction.nh_mmis_requirement_builder import NhMmisRequirementBuilder
        from app.cognos.extraction.nh_mmis_dsd_mapper import map_dsd_to_domain

        canonical_doc = parse_cognos_docx(path)
        nh_interpreter = NhMmisDsdInterpreter(canonical_doc)
        nh_dsd = nh_interpreter.interpret()
        nh_builder = NhMmisRequirementBuilder(nh_dsd, {})
        req_set = nh_builder.build()
        report_def = map_dsd_to_domain(nh_dsd, doc_name)
        return report_def, req_set, nh_dsd
